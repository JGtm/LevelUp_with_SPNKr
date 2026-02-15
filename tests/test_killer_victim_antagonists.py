from __future__ import annotations

from dataclasses import dataclass

from src.analysis import compute_personal_antagonists
from src.analysis.killer_victim import (
    validate_and_adjust_pairs,
)


@dataclass
class MockMatchPlayerStats:
    """Mock pour MatchPlayerStats utilisé dans les tests."""

    xuid: str
    gamertag: str
    kills: int
    deaths: int
    assists: int
    team_id: int | None
    rank: int
    score: int | None = None


class TestKillerVictimAntagonists:
    """Tests du calcul hybride Némésis / Souffre-douleur."""

    def test_hybrid_prefers_certain_then_stable(self) -> None:
        """Attribue les cas ambigus en privilégiant le "certain" (heuristique 2).

        Scénario:
        - Deux morts de moi: une certaine (killer unique), une ambiguë (2 killers).
        - Deux kills de moi: une certaine (victime unique), une ambiguë (2 victimes).

        Attendu:
        - Némésis = killer déjà vu en certain, et compteur marqué estimé (≈).
        - Souffre-douleur = victime déjà vue en certain, et compteur marqué estimé (≈).
        """

        me = "1"

        events = [
            # --- Morts de moi ---
            {"event_type": "death", "type_hint": 20, "time_ms": 1000, "xuid": me, "gamertag": "Me"},
            {"event_type": "death", "type_hint": 20, "time_ms": 2000, "xuid": me, "gamertag": "Me"},
            # Kills candidats (à 1000: ambigu, à 2000: certain)
            {
                "event_type": "kill",
                "type_hint": 50,
                "time_ms": 1000,
                "xuid": "2",
                "gamertag": "KillerA",
            },
            {
                "event_type": "kill",
                "type_hint": 50,
                "time_ms": 1000,
                "xuid": "3",
                "gamertag": "KillerB",
            },
            {
                "event_type": "kill",
                "type_hint": 50,
                "time_ms": 2000,
                "xuid": "2",
                "gamertag": "KillerA",
            },
            # --- Kills de moi ---
            {"event_type": "kill", "type_hint": 50, "time_ms": 3000, "xuid": me, "gamertag": "Me"},
            {"event_type": "kill", "type_hint": 50, "time_ms": 4000, "xuid": me, "gamertag": "Me"},
            # Deaths candidats (à 3000: ambigu, à 4000: certain)
            {
                "event_type": "death",
                "type_hint": 20,
                "time_ms": 3000,
                "xuid": "4",
                "gamertag": "VictimC",
            },
            {
                "event_type": "death",
                "type_hint": 20,
                "time_ms": 3000,
                "xuid": "5",
                "gamertag": "VictimD",
            },
            {
                "event_type": "death",
                "type_hint": 20,
                "time_ms": 4000,
                "xuid": "4",
                "gamertag": "VictimC",
            },
        ]

        res = compute_personal_antagonists(events, me_xuid=me, tolerance_ms=0)

        assert res.nemesis is not None
        assert res.nemesis.xuid == "2"
        assert res.nemesis.opponent_killed_me.total == 2
        assert res.nemesis.opponent_killed_me.certain == 1
        assert res.nemesis.opponent_killed_me.estimated == 1
        assert res.nemesis.opponent_killed_me.has_estimated is True

        assert res.bully is not None
        assert res.bully.xuid == "4"
        assert res.bully.me_killed_opponent.total == 2
        assert res.bully.me_killed_opponent.certain == 1
        assert res.bully.me_killed_opponent.estimated == 1
        assert res.bully.me_killed_opponent.has_estimated is True

        # Sanity: les totaux attribués sont cohérents avec le scénario
        assert res.my_deaths_total == 2
        assert res.my_deaths_assigned_total == 2
        assert res.my_kills_total == 2
        assert res.my_kills_assigned_total == 2

    def test_tiebreaker_uses_rank_when_equal_score(self) -> None:
        """Sprint 3.1: Le tie-breaker par rang est utilisé quand les scores "certain" sont égaux.

        Scénario:
        - Une mort de moi avec 2 killers simultanés (même score certain = 0)
        - KillerA (xuid=2) a le rang 1, KillerB (xuid=3) a le rang 2
        - Attendu: KillerA est choisi car il a le meilleur rang (1 < 2)
        """
        me = "1"

        events = [
            # Mort de moi
            {"event_type": "death", "type_hint": 20, "time_ms": 1000, "xuid": me, "gamertag": "Me"},
            # Deux killers simultanés (égalité parfaite sans certain)
            {
                "event_type": "kill",
                "type_hint": 50,
                "time_ms": 1000,
                "xuid": "2",
                "gamertag": "KillerA",
            },
            {
                "event_type": "kill",
                "type_hint": 50,
                "time_ms": 1000,
                "xuid": "3",
                "gamertag": "KillerB",
            },
        ]

        # Stats officielles avec rangs
        official_stats = [
            MockMatchPlayerStats(
                xuid=me, gamertag="Me", kills=0, deaths=1, assists=0, team_id=0, rank=4
            ),
            MockMatchPlayerStats(
                xuid="2", gamertag="KillerA", kills=5, deaths=2, assists=1, team_id=1, rank=1
            ),  # Meilleur rang
            MockMatchPlayerStats(
                xuid="3", gamertag="KillerB", kills=3, deaths=4, assists=2, team_id=1, rank=2
            ),
        ]

        res = compute_personal_antagonists(
            events, me_xuid=me, tolerance_ms=0, official_stats=official_stats
        )

        assert res.nemesis is not None
        # KillerA (xuid=2) devrait être choisi grâce au tie-breaker par rang
        assert res.nemesis.xuid == "2"
        assert res.nemesis.opponent_killed_me.total == 1
        assert res.nemesis.opponent_killed_me.estimated == 1  # C'est une estimation

    def test_validation_with_official_stats(self) -> None:
        """Sprint 3.1: Validation des résultats avec les stats officielles.

        Scénario:
        - Stats officielles: 2 kills, 1 death
        - Events reconstitués: 2 kills, 1 death (cohérent)
        - Attendu: is_validated=True
        """
        me = "1"

        events = [
            # 1 mort de moi
            {"event_type": "death", "type_hint": 20, "time_ms": 1000, "xuid": me, "gamertag": "Me"},
            {
                "event_type": "kill",
                "type_hint": 50,
                "time_ms": 1000,
                "xuid": "2",
                "gamertag": "KillerA",
            },
            # 2 kills de moi
            {"event_type": "kill", "type_hint": 50, "time_ms": 2000, "xuid": me, "gamertag": "Me"},
            {
                "event_type": "death",
                "type_hint": 20,
                "time_ms": 2000,
                "xuid": "3",
                "gamertag": "VictimB",
            },
            {"event_type": "kill", "type_hint": 50, "time_ms": 3000, "xuid": me, "gamertag": "Me"},
            {
                "event_type": "death",
                "type_hint": 20,
                "time_ms": 3000,
                "xuid": "4",
                "gamertag": "VictimC",
            },
        ]

        # Stats officielles cohérentes
        official_stats = [
            MockMatchPlayerStats(
                xuid=me, gamertag="Me", kills=2, deaths=1, assists=0, team_id=0, rank=2
            ),
            MockMatchPlayerStats(
                xuid="2", gamertag="KillerA", kills=1, deaths=0, assists=0, team_id=1, rank=1
            ),
            MockMatchPlayerStats(
                xuid="3", gamertag="VictimB", kills=0, deaths=1, assists=0, team_id=1, rank=3
            ),
            MockMatchPlayerStats(
                xuid="4", gamertag="VictimC", kills=0, deaths=1, assists=0, team_id=1, rank=4
            ),
        ]

        res = compute_personal_antagonists(
            events, me_xuid=me, tolerance_ms=0, official_stats=official_stats
        )

        assert res.is_validated is True
        assert "Cohérent" in res.validation_notes

    def test_validation_detects_inconsistency(self) -> None:
        """Sprint 3.1: La validation détecte les incohérences.

        Scénario:
        - Stats officielles: 3 kills, 2 deaths
        - Events reconstitués: 2 kills, 1 death (manquent des événements)
        - Attendu: is_validated=False avec notes d'écart
        """
        me = "1"

        events = [
            # 1 mort de moi (mais stats officielles disent 2)
            {"event_type": "death", "type_hint": 20, "time_ms": 1000, "xuid": me, "gamertag": "Me"},
            {
                "event_type": "kill",
                "type_hint": 50,
                "time_ms": 1000,
                "xuid": "2",
                "gamertag": "KillerA",
            },
            # 2 kills de moi (mais stats officielles disent 3)
            {"event_type": "kill", "type_hint": 50, "time_ms": 2000, "xuid": me, "gamertag": "Me"},
            {
                "event_type": "death",
                "type_hint": 20,
                "time_ms": 2000,
                "xuid": "3",
                "gamertag": "VictimB",
            },
            {"event_type": "kill", "type_hint": 50, "time_ms": 3000, "xuid": me, "gamertag": "Me"},
            {
                "event_type": "death",
                "type_hint": 20,
                "time_ms": 3000,
                "xuid": "4",
                "gamertag": "VictimC",
            },
        ]

        # Stats officielles avec écarts
        official_stats = [
            MockMatchPlayerStats(
                xuid=me, gamertag="Me", kills=3, deaths=2, assists=0, team_id=0, rank=2
            ),
            MockMatchPlayerStats(
                xuid="2", gamertag="KillerA", kills=2, deaths=0, assists=0, team_id=1, rank=1
            ),
        ]

        res = compute_personal_antagonists(
            events, me_xuid=me, tolerance_ms=0, official_stats=official_stats
        )

        assert res.is_validated is False
        assert "Écarts" in res.validation_notes
        assert "kills" in res.validation_notes
        assert "deaths" in res.validation_notes


class TestValidateAndAdjustPairs:
    """Tests de la fonction validate_and_adjust_pairs (Sprint 3.1)."""

    def test_consistent_pairs(self) -> None:
        """Les paires cohérentes retournent is_globally_consistent=True."""
        from src.analysis.killer_victim import KVPair

        pairs = [
            KVPair(
                killer_xuid="2",
                killer_gamertag="A",
                victim_xuid="1",
                victim_gamertag="Me",
                time_ms=1000,
            ),
            KVPair(
                killer_xuid="1",
                killer_gamertag="Me",
                victim_xuid="3",
                victim_gamertag="B",
                time_ms=2000,
            ),
        ]

        official_stats = [
            MockMatchPlayerStats(
                xuid="1", gamertag="Me", kills=1, deaths=1, assists=0, team_id=0, rank=2
            ),
            MockMatchPlayerStats(
                xuid="2", gamertag="A", kills=1, deaths=0, assists=0, team_id=1, rank=1
            ),
            MockMatchPlayerStats(
                xuid="3", gamertag="B", kills=0, deaths=1, assists=0, team_id=1, rank=3
            ),
        ]

        results, is_consistent = validate_and_adjust_pairs(pairs, official_stats)

        assert is_consistent is True
        assert len(results) == 3
        assert all(r.is_consistent for r in results)

    def test_inconsistent_pairs(self) -> None:
        """Les paires incohérentes retournent is_globally_consistent=False."""
        from src.analysis.killer_victim import KVPair

        # Une seule paire reconstituée
        pairs = [
            KVPair(
                killer_xuid="2",
                killer_gamertag="A",
                victim_xuid="1",
                victim_gamertag="Me",
                time_ms=1000,
            ),
        ]

        # Mais les stats officielles montrent plus de kills/deaths
        official_stats = [
            MockMatchPlayerStats(
                xuid="1", gamertag="Me", kills=0, deaths=2, assists=0, team_id=0, rank=2
            ),  # 2 morts officielles
            MockMatchPlayerStats(
                xuid="2", gamertag="A", kills=2, deaths=0, assists=0, team_id=1, rank=1
            ),  # 2 kills officiels
        ]

        results, is_consistent = validate_and_adjust_pairs(pairs, official_stats)

        assert is_consistent is False
        # Vérifier les écarts
        me_result = next(r for r in results if r.xuid == "1")
        assert me_result.deaths_reconstituted == 1  # Reconstitué
        assert me_result.deaths_official == 2  # Officiel
        assert me_result.deaths_diff == -1  # Écart

    def test_empty_official_stats(self) -> None:
        """Sans stats officielles, la validation retourne True par défaut."""
        from src.analysis.killer_victim import KVPair

        pairs = [
            KVPair(
                killer_xuid="2",
                killer_gamertag="A",
                victim_xuid="1",
                victim_gamertag="Me",
                time_ms=1000,
            ),
        ]

        results, is_consistent = validate_and_adjust_pairs(pairs, [])

        assert is_consistent is True
        assert len(results) == 0
