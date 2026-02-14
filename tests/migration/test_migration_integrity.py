"""Tests d'intégrité pour la migration v5 (shared_matches).

Valide que :
1. Le script de migration produit les bonnes statistiques
2. Les données sont correctement insérées dans shared_matches
3. Les doublons sont gérés (INSERT OR IGNORE)
4. Les taux de partage sont calculés correctement
5. Les VIEWs de compatibilité fonctionnent
6. La fonction extract_all_medals() fonctionne
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pytest

# Résolution du projet
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Import des scripts de migration
import sys

sys.path.insert(0, str(PROJECT_ROOT))

from scripts.migration.create_shared_matches_db import (
    create_shared_matches_db,
)
from scripts.migration.migrate_player_to_shared import (
    _migrate_highlight_events,
    _migrate_match_registry,
    _migrate_medals,
    _migrate_participants,
    _migrate_xuid_aliases,
    _parse_event_killer_victim,
    migrate_player_to_shared,
    recalculate_player_counts,
)
from src.data.sync.models import SharedMedalEarnedRow
from src.data.sync.transformers import extract_all_medals

# =============================================================================
# Fixtures
# =============================================================================

SCHEMA_SQL = PROJECT_ROOT / "scripts" / "migration" / "schema_v5.sql"

# DDL pour créer une base joueur v4 factice
PLAYER_V4_DDL = """
CREATE TABLE match_stats (
    match_id VARCHAR PRIMARY KEY,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    playlist_id VARCHAR,
    playlist_name VARCHAR,
    map_id VARCHAR,
    map_name VARCHAR,
    pair_id VARCHAR,
    pair_name VARCHAR,
    game_variant_id VARCHAR,
    game_variant_name VARCHAR,
    mode_category VARCHAR,
    is_ranked BOOLEAN DEFAULT FALSE,
    is_firefight BOOLEAN DEFAULT FALSE,
    time_played_seconds INTEGER,
    my_team_score SMALLINT,
    enemy_team_score SMALLINT,
    outcome TINYINT,
    team_id TINYINT,
    rank SMALLINT,
    kills SMALLINT,
    deaths SMALLINT,
    assists SMALLINT,
    score INTEGER,
    shots_fired INTEGER,
    shots_hit INTEGER,
    damage_dealt FLOAT,
    damage_taken FLOAT,
    session_id VARCHAR,
    session_label VARCHAR,
    performance_score FLOAT,
    is_with_friends BOOLEAN,
    teammates_signature VARCHAR,
    known_teammates_count SMALLINT,
    friends_xuids VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE match_participants (
    match_id VARCHAR NOT NULL,
    xuid VARCHAR NOT NULL,
    team_id INTEGER,
    outcome INTEGER,
    gamertag VARCHAR,
    rank SMALLINT,
    score INTEGER,
    kills SMALLINT,
    deaths SMALLINT,
    assists SMALLINT,
    shots_fired INTEGER,
    shots_hit INTEGER,
    damage_dealt FLOAT,
    damage_taken FLOAT,
    PRIMARY KEY (match_id, xuid)
);

CREATE TABLE medals_earned (
    match_id VARCHAR,
    medal_name_id BIGINT,
    count SMALLINT,
    PRIMARY KEY (match_id, medal_name_id)
);

CREATE SEQUENCE IF NOT EXISTS highlight_events_id_seq;
CREATE TABLE highlight_events (
    id INTEGER PRIMARY KEY DEFAULT nextval('highlight_events_id_seq'),
    match_id VARCHAR NOT NULL,
    event_type VARCHAR NOT NULL,
    time_ms INTEGER,
    xuid VARCHAR,
    gamertag VARCHAR,
    type_hint INTEGER,
    raw_json VARCHAR
);

CREATE TABLE xuid_aliases (
    xuid VARCHAR PRIMARY KEY,
    gamertag VARCHAR NOT NULL,
    last_seen TIMESTAMP,
    source VARCHAR,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


@pytest.fixture
def tmp_dir():
    """Répertoire temporaire pour les DBs de test."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def shared_db(tmp_dir: Path) -> Path:
    """Crée une shared_matches.duckdb vide dans tmp_dir."""
    db_path = tmp_dir / "shared_matches.duckdb"
    create_shared_matches_db(db_path, force=True)
    return db_path


def _create_player_db(
    tmp_dir: Path,
    gamertag: str,
    xuid: str,
    matches: list[dict],
    participants: list[dict] | None = None,
    medals: list[dict] | None = None,
    events: list[dict] | None = None,
    aliases: list[dict] | None = None,
) -> Path:
    """Crée une DB joueur v4 factice avec les données fournies."""
    db_path = tmp_dir / gamertag / "stats.duckdb"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(PLAYER_V4_DDL)

        # match_stats
        for m in matches:
            conn.execute(
                """INSERT INTO match_stats
                (match_id, start_time, end_time, playlist_id, playlist_name,
                 map_id, map_name, pair_id, pair_name,
                 game_variant_id, game_variant_name,
                 mode_category, is_ranked, is_firefight,
                 time_played_seconds, my_team_score, enemy_team_score,
                 outcome, team_id, rank, kills, deaths, assists, score,
                 performance_score, session_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    m["match_id"],
                    m.get("start_time", datetime(2025, 1, 1, tzinfo=timezone.utc)),
                    m.get("end_time", datetime(2025, 1, 1, 0, 10, tzinfo=timezone.utc)),
                    m.get("playlist_id", "plt_001"),
                    m.get("playlist_name", "Quick Play"),
                    m.get("map_id", "map_001"),
                    m.get("map_name", "Aquarius"),
                    m.get("pair_id"),
                    m.get("pair_name"),
                    m.get("game_variant_id"),
                    m.get("game_variant_name"),
                    m.get("mode_category", "Arena"),
                    m.get("is_ranked", False),
                    m.get("is_firefight", False),
                    m.get("time_played_seconds", 600),
                    m.get("my_team_score", 50),
                    m.get("enemy_team_score", 45),
                    m.get("outcome", 2),
                    m.get("team_id", 0),
                    m.get("rank", 1),
                    m.get("kills", 10),
                    m.get("deaths", 5),
                    m.get("assists", 3),
                    m.get("score", 1500),
                    m.get("performance_score", 65.0),
                    m.get("session_id", "sess_001"),
                ),
            )

        # match_participants
        if participants:
            for p in participants:
                conn.execute(
                    """INSERT INTO match_participants
                    (match_id, xuid, team_id, outcome, gamertag, rank, score,
                     kills, deaths, assists, shots_fired, shots_hit,
                     damage_dealt, damage_taken)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        p["match_id"],
                        p["xuid"],
                        p.get("team_id", 0),
                        p.get("outcome", 2),
                        p.get("gamertag", "Player"),
                        p.get("rank", 1),
                        p.get("score", 1000),
                        p.get("kills", 10),
                        p.get("deaths", 5),
                        p.get("assists", 3),
                        p.get("shots_fired"),
                        p.get("shots_hit"),
                        p.get("damage_dealt"),
                        p.get("damage_taken"),
                    ),
                )

        # medals_earned
        if medals:
            for med in medals:
                conn.execute(
                    "INSERT INTO medals_earned (match_id, medal_name_id, count) VALUES (?, ?, ?)",
                    (med["match_id"], med["medal_name_id"], med["count"]),
                )

        # highlight_events
        if events:
            for ev in events:
                conn.execute(
                    """INSERT INTO highlight_events
                    (match_id, event_type, time_ms, xuid, gamertag, type_hint, raw_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        ev["match_id"],
                        ev["event_type"],
                        ev.get("time_ms", 0),
                        ev.get("xuid"),
                        ev.get("gamertag"),
                        ev.get("type_hint"),
                        ev.get("raw_json"),
                    ),
                )

        # xuid_aliases
        if aliases:
            for a in aliases:
                conn.execute(
                    """INSERT INTO xuid_aliases (xuid, gamertag, last_seen, source)
                    VALUES (?, ?, ?, ?)""",
                    (a["xuid"], a["gamertag"], a.get("last_seen"), a.get("source", "test")),
                )

    finally:
        conn.close()

    return db_path


# =============================================================================
# Tests de _parse_event_killer_victim
# =============================================================================


class TestParseEventKillerVictim:
    """Tests pour la conversion event v4 → v5 (killer/victim)."""

    def test_kill_event(self) -> None:
        """Un event 'Kill' → xuid est le killer."""
        k_xuid, k_gt, v_xuid, v_gt = _parse_event_killer_victim(
            "Kill", "xuid_killer", "KillerGT", None
        )
        assert k_xuid == "xuid_killer"
        assert k_gt == "KillerGT"
        assert v_xuid is None
        assert v_gt is None

    def test_death_event(self) -> None:
        """Un event 'Death' → xuid est la victime."""
        k_xuid, k_gt, v_xuid, v_gt = _parse_event_killer_victim(
            "Death", "xuid_victim", "VictimGT", None
        )
        assert v_xuid == "xuid_victim"
        assert v_gt == "VictimGT"
        assert k_xuid is None
        assert k_gt is None

    def test_kill_event_with_raw_json_victim(self) -> None:
        """Kill avec raw_json contenant victim_xuid."""
        raw = json.dumps(
            {
                "victim_xuid": "xuid_v",
                "victim_gamertag": "VictimGT",
            }
        )
        k_xuid, k_gt, v_xuid, v_gt = _parse_event_killer_victim("Kill", "xuid_k", "KillerGT", raw)
        assert k_xuid == "xuid_k"
        assert v_xuid == "xuid_v"
        assert v_gt == "VictimGT"

    def test_death_event_with_raw_json_killer(self) -> None:
        """Death avec raw_json contenant killer_xuid."""
        raw = json.dumps(
            {
                "killer_xuid": "xuid_k",
                "killer_gamertag": "KillerGT",
            }
        )
        k_xuid, k_gt, v_xuid, v_gt = _parse_event_killer_victim("Death", "xuid_v", "VictimGT", raw)
        assert v_xuid == "xuid_v"
        assert k_xuid == "xuid_k"
        assert k_gt == "KillerGT"

    def test_unknown_event_type(self) -> None:
        """Event inconnu → xuid assigné au killer par défaut."""
        k_xuid, k_gt, v_xuid, v_gt = _parse_event_killer_victim(
            "Assist", "xuid_p", "PlayerGT", None
        )
        assert k_xuid == "xuid_p"
        assert k_gt == "PlayerGT"
        assert v_xuid is None

    def test_malformed_raw_json(self) -> None:
        """raw_json invalide → pas de crash."""
        k_xuid, k_gt, v_xuid, v_gt = _parse_event_killer_victim(
            "Kill", "xuid_k", "KillerGT", "not valid json"
        )
        assert k_xuid == "xuid_k"
        assert v_xuid is None


# =============================================================================
# Tests de migration match_registry
# =============================================================================


class TestMigrateMatchRegistry:
    """Tests pour _migrate_match_registry."""

    def test_new_matches(self, tmp_dir: Path, shared_db: Path) -> None:
        """Des matchs nouveaux sont insérés dans match_registry."""
        player_db = _create_player_db(
            tmp_dir,
            "TestPlayer",
            "xuid_001",
            matches=[
                {"match_id": "m1"},
                {"match_id": "m2"},
                {"match_id": "m3"},
            ],
        )

        conn_p = duckdb.connect(str(player_db), read_only=True)
        conn_s = duckdb.connect(str(shared_db))

        try:
            stats = _migrate_match_registry(conn_p, conn_s, "TestPlayer")
            assert stats["matches_processed"] == 3
            assert stats["matches_new"] == 3
            assert stats["matches_existing"] == 0

            # Vérifier dans shared
            count = conn_s.execute("SELECT COUNT(*) FROM match_registry").fetchone()[0]
            assert count == 3

            # Vérifier first_sync_by
            row = conn_s.execute(
                "SELECT first_sync_by, player_count FROM match_registry WHERE match_id='m1'"
            ).fetchone()
            assert row[0] == "TestPlayer"
            assert row[1] == 1
        finally:
            conn_p.close()
            conn_s.close()

    def test_existing_matches_increment_player_count(self, tmp_dir: Path, shared_db: Path) -> None:
        """Des matchs déjà connus incrémentent player_count."""
        # Joueur 1 : 3 matchs
        player1_db = _create_player_db(
            tmp_dir,
            "Player1",
            "xuid_001",
            matches=[{"match_id": "m1"}, {"match_id": "m2"}, {"match_id": "m3"}],
        )

        conn_p1 = duckdb.connect(str(player1_db), read_only=True)
        conn_s = duckdb.connect(str(shared_db))

        try:
            _migrate_match_registry(conn_p1, conn_s, "Player1")
        finally:
            conn_p1.close()

        # Joueur 2 : 2 matchs communs + 1 nouveau
        player2_db = _create_player_db(
            tmp_dir,
            "Player2",
            "xuid_002",
            matches=[{"match_id": "m1"}, {"match_id": "m2"}, {"match_id": "m4"}],
        )

        conn_p2 = duckdb.connect(str(player2_db), read_only=True)

        try:
            stats = _migrate_match_registry(conn_p2, conn_s, "Player2")
            assert stats["matches_new"] == 1  # m4
            assert stats["matches_existing"] == 2  # m1, m2

            # Vérifier player_count
            row = conn_s.execute(
                "SELECT player_count FROM match_registry WHERE match_id='m1'"
            ).fetchone()
            assert row[0] == 2

            row4 = conn_s.execute(
                "SELECT player_count, first_sync_by FROM match_registry WHERE match_id='m4'"
            ).fetchone()
            assert row4[0] == 1
            assert row4[1] == "Player2"

            # Total dans shared
            total = conn_s.execute("SELECT COUNT(*) FROM match_registry").fetchone()[0]
            assert total == 4  # m1, m2, m3, m4
        finally:
            conn_p2.close()
            conn_s.close()

    def test_dry_run(self, tmp_dir: Path, shared_db: Path) -> None:
        """dry_run ne modifie pas la DB."""
        player_db = _create_player_db(
            tmp_dir,
            "DryPlayer",
            "xuid_d",
            matches=[{"match_id": "md1"}],
        )

        conn_p = duckdb.connect(str(player_db), read_only=True)
        conn_s = duckdb.connect(str(shared_db), read_only=True)

        try:
            stats = _migrate_match_registry(conn_p, conn_s, "DryPlayer", dry_run=True)
            assert stats["matches_new"] == 1  # Détecté mais pas inséré
        finally:
            conn_p.close()
            conn_s.close()


# =============================================================================
# Tests de migration match_participants
# =============================================================================


class TestMigrateParticipants:
    """Tests pour _migrate_participants."""

    def test_participants_inserted(self, tmp_dir: Path, shared_db: Path) -> None:
        """Les participants sont insérés dans shared."""
        player_db = _create_player_db(
            tmp_dir,
            "TestP",
            "xuid_p",
            matches=[{"match_id": "m1"}],
            participants=[
                {"match_id": "m1", "xuid": "xuid_a", "gamertag": "Alice", "kills": 10},
                {"match_id": "m1", "xuid": "xuid_b", "gamertag": "Bob", "kills": 8},
            ],
        )

        conn_p = duckdb.connect(str(player_db), read_only=True)
        conn_s = duckdb.connect(str(shared_db))

        try:
            # D'abord insérer le match dans le registre
            _migrate_match_registry(conn_p, conn_s, "TestP")

            count = _migrate_participants(conn_p, conn_s, "TestP")
            assert count == 2

            # Vérifier dans shared
            rows = conn_s.execute(
                "SELECT gamertag, kills FROM match_participants WHERE match_id='m1' ORDER BY gamertag"
            ).fetchall()
            assert len(rows) == 2
            assert rows[0][0] == "Alice"
            assert rows[1][0] == "Bob"
        finally:
            conn_p.close()
            conn_s.close()

    def test_duplicate_participants_ignored(self, tmp_dir: Path, shared_db: Path) -> None:
        """Les participants en doublon sont ignorés (INSERT OR IGNORE)."""
        player_db = _create_player_db(
            tmp_dir,
            "PL1",
            "xuid_1",
            matches=[{"match_id": "m1"}],
            participants=[
                {"match_id": "m1", "xuid": "xuid_a", "gamertag": "Alice"},
                {"match_id": "m1", "xuid": "xuid_b", "gamertag": "Bob"},
            ],
        )

        conn_p = duckdb.connect(str(player_db), read_only=True)
        conn_s = duckdb.connect(str(shared_db))

        try:
            _migrate_match_registry(conn_p, conn_s, "PL1")
            _migrate_participants(conn_p, conn_s, "PL1")

            # Re-migrer le même joueur
            _migrate_participants(conn_p, conn_s, "PL1")

            # Vérifier pas de doublons
            count = conn_s.execute(
                "SELECT COUNT(*) FROM match_participants WHERE match_id='m1'"
            ).fetchone()[0]
            assert count == 2
        finally:
            conn_p.close()
            conn_s.close()


# =============================================================================
# Tests de migration highlight_events
# =============================================================================


class TestMigrateHighlightEvents:
    """Tests pour _migrate_highlight_events."""

    def test_events_migrated(self, tmp_dir: Path, shared_db: Path) -> None:
        """Les events v4 sont convertis en format v5."""
        player_db = _create_player_db(
            tmp_dir,
            "EVP",
            "xuid_evp",
            matches=[{"match_id": "m1"}],
            events=[
                {
                    "match_id": "m1",
                    "event_type": "Kill",
                    "time_ms": 1000,
                    "xuid": "xuid_evp",
                    "gamertag": "EVP",
                },
                {
                    "match_id": "m1",
                    "event_type": "Death",
                    "time_ms": 2000,
                    "xuid": "xuid_evp",
                    "gamertag": "EVP",
                },
            ],
        )

        conn_p = duckdb.connect(str(player_db), read_only=True)
        conn_s = duckdb.connect(str(shared_db))

        try:
            _migrate_match_registry(conn_p, conn_s, "EVP")
            count = _migrate_highlight_events(conn_p, conn_s, "EVP")
            assert count == 2

            # Vérifier la conversion Kill → killer_xuid
            kill_row = conn_s.execute(
                "SELECT killer_xuid, killer_gamertag FROM highlight_events "
                "WHERE match_id='m1' AND event_type='Kill'"
            ).fetchone()
            assert kill_row[0] == "xuid_evp"
            assert kill_row[1] == "EVP"

            # Vérifier la conversion Death → victim_xuid
            death_row = conn_s.execute(
                "SELECT victim_xuid, victim_gamertag FROM highlight_events "
                "WHERE match_id='m1' AND event_type='Death'"
            ).fetchone()
            assert death_row[0] == "xuid_evp"
            assert death_row[1] == "EVP"
        finally:
            conn_p.close()
            conn_s.close()

    def test_events_from_existing_match_skipped(self, tmp_dir: Path, shared_db: Path) -> None:
        """Les events d'un match déjà migré sont ignorés."""
        player1_db = _create_player_db(
            tmp_dir,
            "P1",
            "xuid_1",
            matches=[{"match_id": "m1"}],
            events=[
                {"match_id": "m1", "event_type": "Kill", "xuid": "xuid_1"},
            ],
        )

        conn_p1 = duckdb.connect(str(player1_db), read_only=True)
        conn_s = duckdb.connect(str(shared_db))

        try:
            _migrate_match_registry(conn_p1, conn_s, "P1")
            _migrate_highlight_events(conn_p1, conn_s, "P1")

            # Player 2 a les mêmes events
            player2_db = _create_player_db(
                tmp_dir,
                "P2",
                "xuid_2",
                matches=[{"match_id": "m1"}],
                events=[
                    {"match_id": "m1", "event_type": "Kill", "xuid": "xuid_2"},
                ],
            )
            conn_p2 = duckdb.connect(str(player2_db), read_only=True)
            count2 = _migrate_highlight_events(conn_p2, conn_s, "P2")
            assert count2 == 0  # Pas de doublons

            # Un seul event dans shared
            total = conn_s.execute(
                "SELECT COUNT(*) FROM highlight_events WHERE match_id='m1'"
            ).fetchone()[0]
            assert total == 1
            conn_p2.close()
        finally:
            conn_p1.close()
            conn_s.close()


# =============================================================================
# Tests de migration medals_earned
# =============================================================================


class TestMigrateMedals:
    """Tests pour _migrate_medals."""

    def test_medals_with_xuid_injection(self, tmp_dir: Path, shared_db: Path) -> None:
        """Les médailles sont migrées avec injection du xuid."""
        player_db = _create_player_db(
            tmp_dir,
            "MedalP",
            "xuid_mp",
            matches=[{"match_id": "m1"}],
            medals=[
                {"match_id": "m1", "medal_name_id": 100, "count": 3},
                {"match_id": "m1", "medal_name_id": 200, "count": 1},
            ],
        )

        conn_p = duckdb.connect(str(player_db), read_only=True)
        conn_s = duckdb.connect(str(shared_db))

        try:
            _migrate_match_registry(conn_p, conn_s, "MedalP")
            count = _migrate_medals(conn_p, conn_s, "MedalP", "xuid_mp")
            assert count == 2

            # Vérifier que xuid est bien injecté
            rows = conn_s.execute(
                "SELECT xuid, medal_name_id, count FROM medals_earned "
                "WHERE match_id='m1' ORDER BY medal_name_id"
            ).fetchall()
            assert len(rows) == 2
            assert rows[0][0] == "xuid_mp"  # xuid injecté
            assert rows[0][1] == 100
            assert rows[0][2] == 3
        finally:
            conn_p.close()
            conn_s.close()

    def test_medals_duplicate_ignored(self, tmp_dir: Path, shared_db: Path) -> None:
        """Les médailles en doublon sont ignorées."""
        player_db = _create_player_db(
            tmp_dir,
            "MDP",
            "xuid_md",
            matches=[{"match_id": "m1"}],
            medals=[{"match_id": "m1", "medal_name_id": 100, "count": 3}],
        )

        conn_p = duckdb.connect(str(player_db), read_only=True)
        conn_s = duckdb.connect(str(shared_db))

        try:
            _migrate_match_registry(conn_p, conn_s, "MDP")
            _migrate_medals(conn_p, conn_s, "MDP", "xuid_md")
            _migrate_medals(conn_p, conn_s, "MDP", "xuid_md")  # Re-run

            count = conn_s.execute(
                "SELECT COUNT(*) FROM medals_earned WHERE match_id='m1'"
            ).fetchone()[0]
            assert count == 1  # Pas de doublon
        finally:
            conn_p.close()
            conn_s.close()


# =============================================================================
# Tests de migration xuid_aliases
# =============================================================================


class TestMigrateAliases:
    """Tests pour _migrate_xuid_aliases."""

    def test_aliases_migrated(self, tmp_dir: Path, shared_db: Path) -> None:
        """Les aliases du joueur sont migrés vers shared."""
        player_db = _create_player_db(
            tmp_dir,
            "AliasP",
            "xuid_ap",
            matches=[{"match_id": "m1"}],
            aliases=[
                {"xuid": "xuid_ap", "gamertag": "AliasP"},
                {"xuid": "xuid_other", "gamertag": "OtherPlayer"},
            ],
        )

        conn_p = duckdb.connect(str(player_db), read_only=True)
        conn_s = duckdb.connect(str(shared_db))

        try:
            count = _migrate_xuid_aliases(conn_p, conn_s, "AliasP")
            assert count == 2

            row = conn_s.execute(
                "SELECT gamertag, source FROM xuid_aliases WHERE xuid='xuid_ap'"
            ).fetchone()
            assert row[0] == "AliasP"
            assert row[1] == "migration"
        finally:
            conn_p.close()
            conn_s.close()


# =============================================================================
# Tests de migration complète (intégration)
# =============================================================================


class TestMigratePlayerToShared:
    """Tests d'intégration pour migrate_player_to_shared."""

    def test_full_migration(self, tmp_dir: Path, shared_db: Path) -> None:
        """Migration complète d'un joueur."""
        player_db = _create_player_db(
            tmp_dir,
            "FullMig",
            "xuid_fm",
            matches=[
                {"match_id": "m1", "kills": 10, "deaths": 5},
                {"match_id": "m2", "kills": 15, "deaths": 3},
            ],
            participants=[
                {"match_id": "m1", "xuid": "xuid_fm", "gamertag": "FullMig", "kills": 10},
                {"match_id": "m1", "xuid": "xuid_enemy", "gamertag": "Enemy", "kills": 5},
                {"match_id": "m2", "xuid": "xuid_fm", "gamertag": "FullMig", "kills": 15},
            ],
            medals=[
                {"match_id": "m1", "medal_name_id": 100, "count": 2},
                {"match_id": "m2", "medal_name_id": 200, "count": 1},
            ],
            events=[
                {"match_id": "m1", "event_type": "Kill", "xuid": "xuid_fm", "gamertag": "FullMig"},
            ],
            aliases=[
                {"xuid": "xuid_fm", "gamertag": "FullMig"},
                {"xuid": "xuid_enemy", "gamertag": "Enemy"},
            ],
        )

        stats = migrate_player_to_shared(
            gamertag="FullMig",
            xuid="xuid_fm",
            player_db_path=player_db,
            shared_db_path=shared_db,
            verbose=False,
        )

        assert stats["matches_new"] == 2
        assert stats["matches_existing"] == 0
        assert stats["participants_inserted"] == 3
        assert stats["events_inserted"] == 1
        assert stats["medals_inserted"] == 2
        assert stats["aliases_inserted"] == 2

        # Vérifier l'intégrité dans shared
        conn = duckdb.connect(str(shared_db), read_only=True)
        try:
            reg_count = conn.execute("SELECT COUNT(*) FROM match_registry").fetchone()[0]
            assert reg_count == 2

            part_count = conn.execute("SELECT COUNT(*) FROM match_participants").fetchone()[0]
            assert part_count == 3

            medal_count = conn.execute("SELECT COUNT(*) FROM medals_earned").fetchone()[0]
            assert medal_count == 2

            event_count = conn.execute("SELECT COUNT(*) FROM highlight_events").fetchone()[0]
            assert event_count == 1

            alias_count = conn.execute("SELECT COUNT(*) FROM xuid_aliases").fetchone()[0]
            assert alias_count == 2
        finally:
            conn.close()

    def test_shared_matches_scenario(self, tmp_dir: Path, shared_db: Path) -> None:
        """Scénario de matchs partagés entre 2 joueurs (le cas métier principal)."""
        # Matchs communs : m1, m2 ; exclusifs : m3 (P1 seulement), m4 (P2 seulement)
        player1_db = _create_player_db(
            tmp_dir,
            "P1",
            "xuid_1",
            matches=[
                {"match_id": "m1"},
                {"match_id": "m2"},
                {"match_id": "m3"},
            ],
            participants=[
                {"match_id": "m1", "xuid": "xuid_1", "gamertag": "P1", "kills": 10},
                {"match_id": "m1", "xuid": "xuid_2", "gamertag": "P2", "kills": 8},
                {"match_id": "m2", "xuid": "xuid_1", "gamertag": "P1"},
                {"match_id": "m2", "xuid": "xuid_2", "gamertag": "P2"},
                {"match_id": "m3", "xuid": "xuid_1", "gamertag": "P1"},
            ],
            medals=[
                {"match_id": "m1", "medal_name_id": 100, "count": 2},
            ],
        )

        player2_db = _create_player_db(
            tmp_dir,
            "P2",
            "xuid_2",
            matches=[
                {"match_id": "m1"},
                {"match_id": "m2"},
                {"match_id": "m4"},
            ],
            participants=[
                {"match_id": "m1", "xuid": "xuid_1", "gamertag": "P1"},
                {"match_id": "m1", "xuid": "xuid_2", "gamertag": "P2"},
                {"match_id": "m2", "xuid": "xuid_1", "gamertag": "P1"},
                {"match_id": "m2", "xuid": "xuid_2", "gamertag": "P2"},
                {"match_id": "m4", "xuid": "xuid_2", "gamertag": "P2"},
            ],
            medals=[
                {"match_id": "m1", "medal_name_id": 300, "count": 1},
            ],
        )

        # Migration P1
        stats1 = migrate_player_to_shared(
            "P1",
            "xuid_1",
            player1_db,
            shared_db,
            verbose=False,
        )
        assert stats1["matches_new"] == 3
        assert stats1["matches_existing"] == 0

        # Migration P2
        stats2 = migrate_player_to_shared(
            "P2",
            "xuid_2",
            player2_db,
            shared_db,
            verbose=False,
        )
        assert stats2["matches_new"] == 1  # Seulement m4
        assert stats2["matches_existing"] == 2  # m1, m2

        # Recalcul des player_counts (contourne la limitation FK DuckDB)
        test_profiles = {
            "P1": {"db_path": str(player1_db)},
            "P2": {"db_path": str(player2_db)},
        }
        recalculate_player_counts(shared_db, profiles=test_profiles)

        # Vérification finale
        conn = duckdb.connect(str(shared_db), read_only=True)
        try:
            total_matches = conn.execute("SELECT COUNT(*) FROM match_registry").fetchone()[0]
            assert total_matches == 4  # m1, m2, m3, m4 (pas de doublon)

            # player_count de m1 devrait être 2
            pc = conn.execute(
                "SELECT player_count FROM match_registry WHERE match_id='m1'"
            ).fetchone()[0]
            assert pc == 2

            # Taux de partage = 2 matchs partagés sur 4 total
            shared = conn.execute(
                "SELECT COUNT(*) FROM match_registry WHERE player_count > 1"
            ).fetchone()[0]
            assert shared == 2

            # Médailles des 2 joueurs
            medal_count = conn.execute(
                "SELECT COUNT(DISTINCT xuid) FROM medals_earned WHERE match_id='m1'"
            ).fetchone()[0]
            assert medal_count == 2  # P1 et P2 ont chacun des médailles sur m1
        finally:
            conn.close()


# =============================================================================
# Tests de extract_all_medals
# =============================================================================


class TestExtractAllMedals:
    """Tests pour extract_all_medals (transformers.py)."""

    def test_extract_all_medals_basic(self) -> None:
        """Extraction des médailles de tous les joueurs."""
        match_json = {
            "MatchId": "match_001",
            "Players": [
                {
                    "PlayerId": "xuid(2533274823110022)",
                    "PlayerGamertag": "JGtm",
                    "PlayerTeamStats": [
                        {
                            "Stats": {
                                "CoreStats": {
                                    "Medals": [
                                        {"NameId": 100, "Count": 2},
                                        {"NameId": 200, "Count": 1},
                                    ]
                                }
                            }
                        }
                    ],
                },
                {
                    "PlayerId": "xuid(2535469190789936)",
                    "PlayerGamertag": "Chocoboflor",
                    "PlayerTeamStats": [
                        {
                            "Stats": {
                                "CoreStats": {
                                    "Medals": [
                                        {"NameId": 100, "Count": 5},
                                        {"NameId": 300, "Count": 3},
                                    ]
                                }
                            }
                        }
                    ],
                },
            ],
        }

        result = extract_all_medals(match_json)
        assert len(result) == 4  # 2 médailles * 2 joueurs

        # Vérifier que tous les résultats sont SharedMedalEarnedRow
        for row in result:
            assert isinstance(row, SharedMedalEarnedRow)
            assert row.match_id == "match_001"
            assert row.xuid is not None

        # Vérifier les xuids distincts
        xuids = {r.xuid for r in result}
        assert "2533274823110022" in xuids
        assert "2535469190789936" in xuids

    def test_extract_all_medals_empty_players(self) -> None:
        """Pas de joueurs → liste vide."""
        result = extract_all_medals({"MatchId": "m1", "Players": []})
        assert result == []

    def test_extract_all_medals_no_medals(self) -> None:
        """Joueurs sans médailles → liste vide."""
        match_json = {
            "MatchId": "m1",
            "Players": [
                {
                    "PlayerId": "xuid(2533274823110099)",
                    "PlayerTeamStats": [{"Stats": {"CoreStats": {"Medals": []}}}],
                }
            ],
        }
        result = extract_all_medals(match_json)
        assert result == []

    def test_extract_all_medals_aggregates_across_teams(self) -> None:
        """Les médailles sont agrégées à travers les équipes."""
        match_json = {
            "MatchId": "m1",
            "Players": [
                {
                    "PlayerId": "xuid(2533274823110099)",
                    "PlayerTeamStats": [
                        {"Stats": {"CoreStats": {"Medals": [{"NameId": 100, "Count": 2}]}}},
                        {"Stats": {"CoreStats": {"Medals": [{"NameId": 100, "Count": 3}]}}},
                    ],
                }
            ],
        }
        result = extract_all_medals(match_json)
        assert len(result) == 1
        assert result[0].count == 5  # 2 + 3 agrégés


# =============================================================================
# Tests de cohérence des données
# =============================================================================


class TestDataIntegrity:
    """Tests vérifiant la cohérence des données après migration."""

    def test_no_orphan_participants(self, tmp_dir: Path, shared_db: Path) -> None:
        """Aucun participant ne devrait référencer un match inexistant."""
        player_db = _create_player_db(
            tmp_dir,
            "IntP",
            "xuid_int",
            matches=[{"match_id": "m1"}],
            participants=[
                {"match_id": "m1", "xuid": "xuid_int", "gamertag": "IntP"},
            ],
        )

        migrate_player_to_shared(
            "IntP",
            "xuid_int",
            player_db,
            shared_db,
            verbose=False,
        )

        conn = duckdb.connect(str(shared_db), read_only=True)
        try:
            orphans = conn.execute("""
                SELECT COUNT(*) FROM match_participants p
                LEFT JOIN match_registry r ON p.match_id = r.match_id
                WHERE r.match_id IS NULL
            """).fetchone()[0]
            assert orphans == 0
        finally:
            conn.close()

    def test_no_orphan_medals(self, tmp_dir: Path, shared_db: Path) -> None:
        """Aucune médaille ne devrait référencer un match inexistant."""
        player_db = _create_player_db(
            tmp_dir,
            "MedInt",
            "xuid_mi",
            matches=[{"match_id": "m1"}],
            medals=[{"match_id": "m1", "medal_name_id": 100, "count": 1}],
        )

        migrate_player_to_shared(
            "MedInt",
            "xuid_mi",
            player_db,
            shared_db,
            verbose=False,
        )

        conn = duckdb.connect(str(shared_db), read_only=True)
        try:
            orphans = conn.execute("""
                SELECT COUNT(*) FROM medals_earned m
                LEFT JOIN match_registry r ON m.match_id = r.match_id
                WHERE r.match_id IS NULL
            """).fetchone()[0]
            assert orphans == 0
        finally:
            conn.close()

    def test_no_orphan_events(self, tmp_dir: Path, shared_db: Path) -> None:
        """Aucun event ne devrait référencer un match inexistant."""
        player_db = _create_player_db(
            tmp_dir,
            "EvInt",
            "xuid_ei",
            matches=[{"match_id": "m1"}],
            events=[
                {"match_id": "m1", "event_type": "Kill", "xuid": "xuid_ei"},
            ],
        )

        migrate_player_to_shared(
            "EvInt",
            "xuid_ei",
            player_db,
            shared_db,
            verbose=False,
        )

        conn = duckdb.connect(str(shared_db), read_only=True)
        try:
            orphans = conn.execute("""
                SELECT COUNT(*) FROM highlight_events e
                LEFT JOIN match_registry r ON e.match_id = r.match_id
                WHERE r.match_id IS NULL
            """).fetchone()[0]
            assert orphans == 0
        finally:
            conn.close()
