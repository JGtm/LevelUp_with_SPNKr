from __future__ import annotations

from src.analysis import compute_personal_antagonists


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
            {"event_type": "kill", "type_hint": 50, "time_ms": 1000, "xuid": "2", "gamertag": "KillerA"},
            {"event_type": "kill", "type_hint": 50, "time_ms": 1000, "xuid": "3", "gamertag": "KillerB"},
            {"event_type": "kill", "type_hint": 50, "time_ms": 2000, "xuid": "2", "gamertag": "KillerA"},
            # --- Kills de moi ---
            {"event_type": "kill", "type_hint": 50, "time_ms": 3000, "xuid": me, "gamertag": "Me"},
            {"event_type": "kill", "type_hint": 50, "time_ms": 4000, "xuid": me, "gamertag": "Me"},
            # Deaths candidats (à 3000: ambigu, à 4000: certain)
            {"event_type": "death", "type_hint": 20, "time_ms": 3000, "xuid": "4", "gamertag": "VictimC"},
            {"event_type": "death", "type_hint": 20, "time_ms": 3000, "xuid": "5", "gamertag": "VictimD"},
            {"event_type": "death", "type_hint": 20, "time_ms": 4000, "xuid": "4", "gamertag": "VictimC"},
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
