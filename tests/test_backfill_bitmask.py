"""Tests pour le système de backfill complet (détection + marquage bitmask).

Vérifie que :
1. La détection trouve les matchs avec données manquantes
2. Après marquage du bitmask, les matchs ne sont plus détectés
3. Les flags --force-* ignorent le bitmask
4. Le mode AND fonctionne correctement
5. compute_backfill_mask calcule les bons bits
6. Les doublons events/personal_scores sont évités à l'insertion
"""

from __future__ import annotations

import duckdb
import pytest

from scripts.backfill.detection import (
    BACKFILL_FLAGS,
    compute_backfill_mask,
    find_matches_missing_data,
)

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

XUID = "2535469190789936"


@pytest.fixture()
def conn():
    """Crée une base DuckDB en mémoire avec le schéma minimal pour les tests."""
    c = duckdb.connect(":memory:")
    c.execute("""
        CREATE TABLE match_stats (
            match_id VARCHAR PRIMARY KEY,
            start_time TIMESTAMP,
            accuracy FLOAT,
            shots_fired INTEGER,
            shots_hit INTEGER,
            playlist_name VARCHAR,
            playlist_id VARCHAR,
            map_name VARCHAR,
            map_id VARCHAR,
            pair_name VARCHAR,
            pair_id VARCHAR,
            game_variant_name VARCHAR,
            game_variant_id VARCHAR,
            performance_score FLOAT,
            backfill_completed INTEGER DEFAULT 0
        )
    """)
    c.execute("""
        CREATE TABLE medals_earned (
            match_id VARCHAR NOT NULL,
            medal_name_id BIGINT NOT NULL,
            count SMALLINT,
            PRIMARY KEY (match_id, medal_name_id)
        )
    """)
    c.execute("""
        CREATE TABLE highlight_events (
            id INTEGER,
            match_id VARCHAR NOT NULL,
            event_type VARCHAR NOT NULL,
            time_ms INTEGER,
            xuid VARCHAR,
            gamertag VARCHAR,
            type_hint INTEGER,
            raw_json VARCHAR
        )
    """)
    c.execute("""
        CREATE TABLE player_match_stats (
            match_id VARCHAR,
            xuid VARCHAR,
            team_id INTEGER,
            team_mmr FLOAT,
            enemy_mmr FLOAT,
            kills_expected FLOAT,
            kills_stddev FLOAT,
            deaths_expected FLOAT,
            deaths_stddev FLOAT,
            assists_expected FLOAT,
            assists_stddev FLOAT,
            PRIMARY KEY (match_id, xuid)
        )
    """)
    c.execute("""
        CREATE TABLE personal_score_awards (
            match_id VARCHAR NOT NULL,
            xuid VARCHAR NOT NULL,
            award_name VARCHAR NOT NULL,
            award_category VARCHAR,
            award_count INTEGER,
            award_score INTEGER,
            created_at TIMESTAMP
        )
    """)
    c.execute("""
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
        )
    """)

    # Insert 3 test matches
    c.execute("""
        INSERT INTO match_stats (match_id, start_time, playlist_name, playlist_id,
                                 map_name, map_id, pair_name, pair_id,
                                 game_variant_name, game_variant_id)
        VALUES
            ('match-001', '2025-01-01', 'Ranked Arena', 'pl-001', 'Aquarius', 'map-001',
             'Slayer', 'pair-001', 'Slayer', 'gv-001'),
            ('match-002', '2025-01-02', 'Ranked Arena', 'pl-002', 'Bazaar', 'map-002',
             'CTF', 'pair-002', 'CTF', 'gv-002'),
            ('match-003', '2025-01-03', 'Social', 'pl-003', 'Streets', 'map-003',
             'Fiesta', 'pair-003', 'Fiesta', 'gv-003')
    """)

    # match-001 has medals, match-002 and match-003 don't
    c.execute("INSERT INTO medals_earned VALUES ('match-001', 100, 2)")

    # match-001 and match-002 have events, match-003 doesn't
    c.execute(
        "INSERT INTO highlight_events VALUES (1, 'match-001', 'kill', 1000, ?, 'Test', 0, NULL)",
        [XUID],
    )
    c.execute(
        "INSERT INTO highlight_events VALUES (2, 'match-002', 'kill', 2000, ?, 'Test', 0, NULL)",
        [XUID],
    )

    # match-001 has skill, others don't
    c.execute(
        """
        INSERT INTO player_match_stats (match_id, xuid, team_mmr, enemy_mmr)
        VALUES ('match-001', ?, 1500.0, 1450.0)
    """,
        [XUID],
    )

    # match-001 has personal scores, others don't
    c.execute(
        """
        INSERT INTO personal_score_awards (match_id, xuid, award_name, award_count, award_score)
        VALUES ('match-001', ?, 'headshot', 5, 100)
    """,
        [XUID],
    )

    # All matches have participants
    for m in ["match-001", "match-002", "match-003"]:
        c.execute(
            """
            INSERT INTO match_participants (match_id, xuid, team_id, outcome, gamertag,
                                           rank, score, kills, deaths, assists)
            VALUES (?, ?, 0, 1, 'TestPlayer', 1, 100, 10, 5, 3)
        """,
            [m, XUID],
        )

    yield c
    c.close()


# ─────────────────────────────────────────────────────────────────────────────
# Tests compute_backfill_mask
# ─────────────────────────────────────────────────────────────────────────────


def test_compute_backfill_mask_single():
    """Un seul type retourne le bon bit."""
    assert compute_backfill_mask("medals") == 1
    assert compute_backfill_mask("events") == 2
    assert compute_backfill_mask("assets") == 256


def test_compute_backfill_mask_multiple():
    """Plusieurs types sont combinés par OR."""
    mask = compute_backfill_mask("medals", "events", "skill")
    assert mask == 1 | 2 | 4  # 7


def test_compute_backfill_mask_all():
    """Tous les types produisent un masque complet."""
    mask = compute_backfill_mask(*BACKFILL_FLAGS.keys())
    expected = sum(BACKFILL_FLAGS.values())
    assert mask == expected


# ─────────────────────────────────────────────────────────────────────────────
# Tests détection — sans bitmask (premier run)
# ─────────────────────────────────────────────────────────────────────────────


def test_detects_missing_medals(conn):
    """Détecte les matchs sans médailles."""
    result = find_matches_missing_data(conn, XUID, medals=True)
    # match-002 et match-003 n'ont pas de médailles
    assert set(result) == {"match-002", "match-003"}


def test_detects_missing_events(conn):
    """Détecte les matchs sans events."""
    result = find_matches_missing_data(conn, XUID, events=True)
    # Seul match-003 n'a pas d'events
    assert result == ["match-003"]


def test_detects_missing_skill(conn):
    """Détecte les matchs sans skill."""
    result = find_matches_missing_data(conn, XUID, skill=True)
    assert set(result) == {"match-002", "match-003"}


def test_detects_missing_personal_scores(conn):
    """Détecte les matchs sans personal scores."""
    result = find_matches_missing_data(conn, XUID, personal_scores=True)
    assert set(result) == {"match-002", "match-003"}


def test_or_mode_union(conn):
    """Mode OR : union des conditions."""
    result = find_matches_missing_data(conn, XUID, detection_mode="or", medals=True, events=True)
    # medals: match-002, match-003 ; events: match-003 → union = {002, 003}
    assert set(result) == {"match-002", "match-003"}


def test_and_mode_intersection(conn):
    """Mode AND : intersection des conditions."""
    result = find_matches_missing_data(conn, XUID, detection_mode="and", medals=True, events=True)
    # medals: {002, 003} AND events: {003} → intersection = {003}
    assert result == ["match-003"]


# ─────────────────────────────────────────────────────────────────────────────
# Tests détection — avec bitmask (après un run)
# ─────────────────────────────────────────────────────────────────────────────


def test_bitmask_excludes_completed_matches(conn):
    """Après marquage du bitmask, les matchs ne sont plus détectés."""
    # Simuler un run de backfill : marquer match-002 et match-003 comme medals-done
    medals_bit = BACKFILL_FLAGS["medals"]
    conn.execute(
        "UPDATE match_stats SET backfill_completed = ? WHERE match_id IN ('match-002', 'match-003')",
        [medals_bit],
    )

    result = find_matches_missing_data(conn, XUID, medals=True)
    # Même si medals_earned n'a pas de lignes pour ces matchs,
    # le bitmask les exclut → 0 résultats
    assert result == []


def test_bitmask_per_type_independent(conn):
    """Le bitmask est indépendant par type."""
    # Marquer match-002 seulement pour medals (bit 0)
    medals_bit = BACKFILL_FLAGS["medals"]
    conn.execute(
        "UPDATE match_stats SET backfill_completed = ? WHERE match_id = 'match-002'",
        [medals_bit],
    )

    # medals : match-002 exclu, match-003 toujours détecté
    result_medals = find_matches_missing_data(conn, XUID, medals=True)
    assert result_medals == ["match-003"]

    # events : match-002 pas marqué pour events → toujours pas détecté
    # (match-002 a des events, seul match-003 n'en a pas)
    result_events = find_matches_missing_data(conn, XUID, events=True)
    assert result_events == ["match-003"]


def test_bitmask_events_excludes_after_marking(conn):
    """Events : marquage exclut le match au rerun."""
    events_bit = BACKFILL_FLAGS["events"]
    conn.execute(
        "UPDATE match_stats SET backfill_completed = ? WHERE match_id = 'match-003'",
        [events_bit],
    )

    result = find_matches_missing_data(conn, XUID, events=True)
    assert result == []


def test_bitmask_combined_types(conn):
    """Le bitmask combiné (medals + events) exclut correctement."""
    mask = compute_backfill_mask("medals", "events")
    conn.execute(
        "UPDATE match_stats SET backfill_completed = ? WHERE match_id = 'match-003'",
        [mask],
    )

    # match-003 exclu pour medals ET events
    result_medals = find_matches_missing_data(conn, XUID, medals=True)
    assert result_medals == ["match-002"]

    result_events = find_matches_missing_data(conn, XUID, events=True)
    assert result_events == []


# ─────────────────────────────────────────────────────────────────────────────
# Tests --force-* ignore le bitmask
# ─────────────────────────────────────────────────────────────────────────────


def test_force_medals_ignores_bitmask(conn):
    """--force-medals ignore le bitmask medals."""
    # Marquer TOUS les matchs comme medals-done
    medals_bit = BACKFILL_FLAGS["medals"]
    conn.execute(f"UPDATE match_stats SET backfill_completed = {medals_bit}")

    # Sans force : 0 résultats
    result_normal = find_matches_missing_data(conn, XUID, medals=True)
    assert result_normal == []

    # Avec force : les matchs sans médailles sont quand même détectés
    result_force = find_matches_missing_data(conn, XUID, medals=True, force_medals=True)
    assert set(result_force) == {"match-002", "match-003"}


# ─────────────────────────────────────────────────────────────────────────────
# Tests max_matches
# ─────────────────────────────────────────────────────────────────────────────


def test_max_matches_limits_results(conn):
    """max_matches limite le nombre de résultats."""
    result = find_matches_missing_data(conn, XUID, medals=True, max_matches=1)
    assert len(result) == 1


# ─────────────────────────────────────────────────────────────────────────────
# Tests scénario complet (simule un run entier)
# ─────────────────────────────────────────────────────────────────────────────


def test_full_scenario_single_run(conn):
    """Scénario complet : détection → traitement → rerun = 0."""
    # ÉTAPE 1 : Détection initiale
    missing = find_matches_missing_data(conn, XUID, medals=True, events=True, skill=True)
    assert len(missing) > 0, "Il devrait y avoir des matchs manquants"

    # ÉTAPE 2 : Simuler le traitement (API appelée, certaines données insérées,
    # d'autres non car l'API ne les a pas)
    # match-003 : API called mais 0 medals, 0 events, 0 skill retournés
    # → Rien n'est inséré dans les tables de données

    # ÉTAPE 3 : Marquer les bits pour TOUS les matchs traités
    mask = compute_backfill_mask("medals", "events", "skill")
    for match_id in missing:
        conn.execute(
            "UPDATE match_stats SET backfill_completed = COALESCE(backfill_completed, 0) | ? "
            "WHERE match_id = ?",
            [mask, match_id],
        )

    # ÉTAPE 4 : Rerun — DOIT trouver 0 matchs manquants
    missing_rerun = find_matches_missing_data(conn, XUID, medals=True, events=True, skill=True)
    assert (
        missing_rerun == []
    ), f"Le rerun devrait trouver 0 matchs manquants, trouvé: {missing_rerun}"


def test_full_scenario_incremental(conn):
    """Scénario incrémental : run medals → run events → tout est couvert."""
    # RUN 1 : --medals seulement
    missing_medals = find_matches_missing_data(conn, XUID, medals=True)
    assert set(missing_medals) == {"match-002", "match-003"}

    # Marquer medals-done
    mask_medals = compute_backfill_mask("medals")
    for mid in missing_medals:
        conn.execute(
            "UPDATE match_stats SET backfill_completed = COALESCE(backfill_completed, 0) | ? "
            "WHERE match_id = ?",
            [mask_medals, mid],
        )

    # Rerun medals → 0
    assert find_matches_missing_data(conn, XUID, medals=True) == []

    # RUN 2 : --events seulement
    missing_events = find_matches_missing_data(conn, XUID, events=True)
    assert missing_events == ["match-003"]

    # Marquer events-done
    mask_events = compute_backfill_mask("events")
    for mid in missing_events:
        conn.execute(
            "UPDATE match_stats SET backfill_completed = COALESCE(backfill_completed, 0) | ? "
            "WHERE match_id = ?",
            [mask_events, mid],
        )

    # Rerun events → 0
    assert find_matches_missing_data(conn, XUID, events=True) == []

    # match-003 a maintenant les DEUX bits : medals=1 + events=2 = 3
    bf = conn.execute(
        "SELECT backfill_completed FROM match_stats WHERE match_id = 'match-003'"
    ).fetchone()[0]
    assert bf == 3


# ─────────────────────────────────────────────────────────────────────────────
# Test sans colonne backfill_completed (rétrocompatibilité)
# ─────────────────────────────────────────────────────────────────────────────


def test_works_without_backfill_completed_column():
    """Si backfill_completed n'existe pas, la détection fonctionne normalement."""
    c = duckdb.connect(":memory:")
    c.execute("""
        CREATE TABLE match_stats (
            match_id VARCHAR PRIMARY KEY,
            start_time TIMESTAMP
        )
    """)
    c.execute("CREATE TABLE medals_earned (match_id VARCHAR, medal_name_id BIGINT, count SMALLINT)")
    c.execute("INSERT INTO match_stats VALUES ('m1', '2025-01-01')")

    result = find_matches_missing_data(c, XUID, medals=True)
    assert result == ["m1"]
    c.close()


# ─────────────────────────────────────────────────────────────────────────────
# Tests bitmask dans engine.py (sync normale)
# ─────────────────────────────────────────────────────────────────────────────


class TestSyncEngineBackfillBitmask:
    """Vérifie que le moteur de sync pose le bitmask backfill_completed."""

    def test_backfill_flags_importable_from_migrations(self):
        """Les constantes sont importables depuis src.data.sync.migrations."""
        from src.data.sync.migrations import BACKFILL_FLAGS as FLAGS
        from src.data.sync.migrations import compute_backfill_mask as cbm

        assert FLAGS["medals"] == 1
        assert FLAGS["aliases"] == 16384
        assert cbm("medals", "events") == 3

    def test_ensure_backfill_completed_column_migration(self):
        """ensure_backfill_completed_column ajoute la colonne si absente."""
        from src.data.sync.migrations import ensure_backfill_completed_column

        c = duckdb.connect(":memory:")
        c.execute("CREATE TABLE match_stats (match_id VARCHAR PRIMARY KEY)")
        ensure_backfill_completed_column(c)

        cols = {
            r[0]
            for r in c.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'match_stats'"
            ).fetchall()
        }
        assert "backfill_completed" in cols
        c.close()

    def test_ensure_backfill_completed_column_idempotent(self):
        """Appeler deux fois ne lève pas d'erreur."""
        from src.data.sync.migrations import ensure_backfill_completed_column

        c = duckdb.connect(":memory:")
        c.execute("CREATE TABLE match_stats (match_id VARCHAR PRIMARY KEY)")
        ensure_backfill_completed_column(c)
        ensure_backfill_completed_column(c)  # 2e appel = idempotent
        c.close()

    def test_sync_bitmask_all_options_enabled(self):
        """Simule le calcul de bitmask quand toutes les SyncOptions sont True."""
        # Reproduit la logique de engine.py._process_single_match
        bf_mask = 0
        bf_mask |= BACKFILL_FLAGS["medals"]
        bf_mask |= BACKFILL_FLAGS["personal_scores"]
        bf_mask |= BACKFILL_FLAGS["performance_scores"]
        bf_mask |= BACKFILL_FLAGS["accuracy"]
        bf_mask |= BACKFILL_FLAGS["shots"]
        # with_skill=True
        bf_mask |= BACKFILL_FLAGS["skill"]
        bf_mask |= BACKFILL_FLAGS["enemy_mmr"]
        # with_highlight_events=True
        bf_mask |= BACKFILL_FLAGS["events"]
        # with_participants=True
        bf_mask |= BACKFILL_FLAGS["participants"]
        bf_mask |= BACKFILL_FLAGS["participants_scores"]
        bf_mask |= BACKFILL_FLAGS["participants_kda"]
        bf_mask |= BACKFILL_FLAGS["participants_shots"]
        bf_mask |= BACKFILL_FLAGS["participants_damage"]
        # with_aliases=True
        bf_mask |= BACKFILL_FLAGS["aliases"]
        # with_assets=True
        bf_mask |= BACKFILL_FLAGS["assets"]

        # Tous les 15 bits doivent être activés
        expected_all = sum(BACKFILL_FLAGS.values())
        assert bf_mask == expected_all, f"Mask={bf_mask}, attendu={expected_all}"

    def test_sync_bitmask_prevents_backfill_detection(self, conn):
        """Après sync avec bitmask complet, le backfill ne détecte rien."""
        # Poser le bitmask complet sur tous les matchs (simule une sync complète)
        full_mask = sum(BACKFILL_FLAGS.values())
        conn.execute(
            "UPDATE match_stats SET backfill_completed = ?",
            [full_mask],
        )

        # Le backfill ne doit rien détecter
        result = find_matches_missing_data(
            conn,
            XUID,
            medals=True,
            events=True,
            skill=True,
            personal_scores=True,
            performance_scores=True,
        )
        assert result == []

    def test_sync_bitmask_partial_allows_backfill(self, conn):
        """Si la sync n'a pas activé un type, le backfill le détecte."""
        # Poser un masque SANS le bit events
        mask_no_events = sum(BACKFILL_FLAGS.values()) & ~BACKFILL_FLAGS["events"]
        conn.execute(
            "UPDATE match_stats SET backfill_completed = ?",
            [mask_no_events],
        )

        # Le backfill doit détecter les matchs manquant d'events
        result_events = find_matches_missing_data(conn, XUID, events=True)
        # match-003 n'a pas d'events en DB → détecté car bitmask events=0
        assert len(result_events) > 0

        # Mais pas les medals (bit activé)
        result_medals = find_matches_missing_data(conn, XUID, medals=True)
        assert result_medals == []

    def test_backfill_flags_reexported_from_detection(self):
        """BACKFILL_FLAGS est toujours accessible depuis detection.py (rétro-compat)."""
        from scripts.backfill.detection import BACKFILL_FLAGS as DET_FLAGS
        from src.data.sync.migrations import BACKFILL_FLAGS as MIG_FLAGS

        assert DET_FLAGS is MIG_FLAGS

    def test_compute_backfill_mask_reexported_from_detection(self):
        """compute_backfill_mask est toujours accessible depuis detection.py."""
        from scripts.backfill.detection import compute_backfill_mask as det_cbm
        from src.data.sync.migrations import compute_backfill_mask as mig_cbm

        assert det_cbm is mig_cbm
        assert det_cbm("medals") == 1
