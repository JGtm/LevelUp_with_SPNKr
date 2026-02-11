"""Tests pour l'extraction et le stockage de damage_dealt/damage_taken des participants.

Sprint 3A : Vérifier que extract_participants() extrait correctement les données
de damage depuis le JSON API (CoreStats.DamageDealt / DamageTaken).
"""

from __future__ import annotations

import pytest

from src.data.sync.models import MatchParticipantRow
from src.data.sync.transformers import extract_participants

# =============================================================================
# Fixtures JSON réalistes
# =============================================================================


def _make_match_json(
    *,
    match_id: str = "test-match-001",
    damage_dealt: float | None = 1500.5,
    damage_taken: float | None = 1200.3,
    include_core_stats: bool = True,
) -> dict:
    """Crée un JSON de match réaliste avec données damage."""
    core_stats = {}
    if include_core_stats:
        core_stats = {
            "Kills": 10,
            "Deaths": 5,
            "Assists": 3,
            "ShotsFired": 200,
            "ShotsHit": 100,
            "Accuracy": 50.0,
        }
        if damage_dealt is not None:
            core_stats["DamageDealt"] = damage_dealt
        if damage_taken is not None:
            core_stats["DamageTaken"] = damage_taken

    player = {
        "PlayerId": "xuid(12345678901234567)",
        "LastTeamId": 0,
        "Outcome": 2,
        "PlayerGamertag": "TestPlayer",
        "Rank": 1,
        "PlayerTeamStats": [
            {
                "Stats": {
                    "CoreStats": core_stats,
                },
            }
        ],
    }

    if not include_core_stats:
        player["PlayerTeamStats"] = []

    return {
        "MatchId": match_id,
        "Players": [player],
    }


def _make_multi_player_json(*, match_id: str = "test-match-multi") -> dict:
    """Crée un JSON avec plusieurs joueurs ayant des damage différents."""
    players = [
        {
            "PlayerId": "xuid(11111111111111111)",
            "LastTeamId": 0,
            "Outcome": 2,
            "PlayerGamertag": "Player1",
            "PlayerTeamStats": [
                {
                    "Stats": {
                        "CoreStats": {
                            "Kills": 15,
                            "Deaths": 3,
                            "Assists": 5,
                            "ShotsFired": 300,
                            "ShotsHit": 150,
                            "DamageDealt": 2500.0,
                            "DamageTaken": 800.0,
                        }
                    }
                }
            ],
        },
        {
            "PlayerId": "xuid(22222222222222222)",
            "LastTeamId": 1,
            "Outcome": 3,
            "PlayerGamertag": "Player2",
            "PlayerTeamStats": [
                {
                    "Stats": {
                        "CoreStats": {
                            "Kills": 5,
                            "Deaths": 12,
                            "Assists": 2,
                            "ShotsFired": 150,
                            "ShotsHit": 60,
                            "DamageDealt": 900.5,
                            "DamageTaken": 2100.0,
                        }
                    }
                }
            ],
        },
    ]

    return {
        "MatchId": match_id,
        "Players": players,
    }


# =============================================================================
# Tests
# =============================================================================


class TestExtractParticipantsDamage:
    """Tests pour l'extraction damage dans extract_participants()."""

    def test_damage_extracted_from_core_stats(self):
        """Vérifie que damage_dealt et damage_taken sont extraits depuis CoreStats."""
        json_data = _make_match_json(damage_dealt=1500.5, damage_taken=1200.3)
        rows = extract_participants(json_data)

        assert len(rows) == 1
        assert rows[0].damage_dealt == pytest.approx(1500.5)
        assert rows[0].damage_taken == pytest.approx(1200.3)

    def test_damage_none_when_missing_from_core_stats(self):
        """Vérifie que damage est None si absent du JSON."""
        json_data = _make_match_json(damage_dealt=None, damage_taken=None)
        rows = extract_participants(json_data)

        assert len(rows) == 1
        assert rows[0].damage_dealt is None
        assert rows[0].damage_taken is None

    def test_damage_none_when_no_core_stats(self):
        """Vérifie que damage est None si CoreStats absent."""
        json_data = _make_match_json(include_core_stats=False)
        rows = extract_participants(json_data)

        assert len(rows) == 1
        assert rows[0].damage_dealt is None
        assert rows[0].damage_taken is None

    def test_damage_zero_is_valid(self):
        """Vérifie que damage_dealt=0 est stocké (pas remplacé par None)."""
        json_data = _make_match_json(damage_dealt=0.0, damage_taken=0.0)
        rows = extract_participants(json_data)

        assert len(rows) == 1
        assert rows[0].damage_dealt == pytest.approx(0.0)
        assert rows[0].damage_taken == pytest.approx(0.0)

    def test_multi_player_damage(self):
        """Vérifie l'extraction damage pour plusieurs joueurs."""
        json_data = _make_multi_player_json()
        rows = extract_participants(json_data)

        assert len(rows) == 2

        # Trié par score décroissant (Player1 a plus de kills)
        player1 = next(r for r in rows if r.gamertag == "Player1")
        player2 = next(r for r in rows if r.gamertag == "Player2")

        assert player1.damage_dealt == pytest.approx(2500.0)
        assert player1.damage_taken == pytest.approx(800.0)
        assert player2.damage_dealt == pytest.approx(900.5)
        assert player2.damage_taken == pytest.approx(2100.0)

    def test_damage_positive_values(self):
        """Vérifie que les valeurs damage extraites sont des floats positifs ou None."""
        json_data = _make_match_json(damage_dealt=1500.5, damage_taken=1200.3)
        rows = extract_participants(json_data)

        for row in rows:
            if row.damage_dealt is not None:
                assert isinstance(row.damage_dealt, float)
                assert row.damage_dealt >= 0
            if row.damage_taken is not None:
                assert isinstance(row.damage_taken, float)
                assert row.damage_taken >= 0

    def test_existing_fields_still_extracted(self):
        """Vérifie que l'ajout de damage ne casse pas les champs existants."""
        json_data = _make_match_json(damage_dealt=1500.5, damage_taken=1200.3)
        rows = extract_participants(json_data)

        assert len(rows) == 1
        row = rows[0]
        assert row.match_id == "test-match-001"
        assert row.xuid == "12345678901234567"
        assert row.kills == 10
        assert row.deaths == 5
        assert row.assists == 3
        assert row.shots_fired == 200
        assert row.shots_hit == 100
        assert row.gamertag == "TestPlayer"


class TestMatchParticipantRowDamage:
    """Tests pour les champs damage du modèle MatchParticipantRow."""

    def test_model_accepts_damage_fields(self):
        """Vérifie que le modèle accepte damage_dealt et damage_taken."""
        row = MatchParticipantRow(
            match_id="test",
            xuid="123",
            damage_dealt=1500.5,
            damage_taken=1200.3,
        )
        assert row.damage_dealt == pytest.approx(1500.5)
        assert row.damage_taken == pytest.approx(1200.3)

    def test_model_defaults_to_none(self):
        """Vérifie que damage est None par défaut."""
        row = MatchParticipantRow(match_id="test", xuid="123")
        assert row.damage_dealt is None
        assert row.damage_taken is None
