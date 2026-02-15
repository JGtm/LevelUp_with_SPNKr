"""Tests unitaires pour l'extraction de enemy_mmr depuis TeamMmrs."""

import pytest

from src.data.sync.transformers import _extract_mmr_from_skill


class TestExtractMMRFromSkill:
    """Tests pour _extract_mmr_from_skill()."""

    def test_extract_mmr_with_teammmrs(self):
        """Test extraction depuis TeamMmrs (méthode recommandée)."""
        skill_json = {
            "Value": [
                {
                    "Id": "xuid(1234567890123456)",
                    "Result": {
                        "TeamId": 0,
                        "TeamMmr": 1500.5,
                        "TeamMmrs": {"0": 1500.5, "1": 1450.3},
                    },
                },
                {
                    "Id": "xuid(9876543210987654)",
                    "Result": {
                        "TeamId": 1,
                        "TeamMmr": 1450.3,
                        "TeamMmrs": {"0": 1500.5, "1": 1450.3},
                    },
                },
            ]
        }

        result = _extract_mmr_from_skill(skill_json, "1234567890123456", 0)
        assert result is not None
        team_mmr, enemy_mmr = result
        assert team_mmr == 1500.5
        assert enemy_mmr == 1450.3

    def test_extract_mmr_fallback_from_other_players(self):
        """Test fallback : extraction depuis TeamMmr des autres joueurs si TeamMmrs absent."""
        skill_json = {
            "Value": [
                {
                    "Id": "xuid(1234567890123456)",
                    "Result": {
                        "TeamId": 0,
                        "TeamMmr": 1500.5,
                        # Pas de TeamMmrs
                    },
                },
                {
                    "Id": "xuid(9876543210987654)",
                    "Result": {
                        "TeamId": 1,
                        "TeamMmr": 1450.3,
                    },
                },
                {
                    "Id": "xuid(1111111111111111)",
                    "Result": {
                        "TeamId": 1,
                        "TeamMmr": 1440.0,
                    },
                },
            ]
        }

        result = _extract_mmr_from_skill(skill_json, "1234567890123456", 0)
        assert result is not None
        team_mmr, enemy_mmr = result
        assert team_mmr == 1500.5
        # enemy_mmr devrait être la moyenne de 1450.3 et 1440.0
        assert enemy_mmr == pytest.approx(1445.15, abs=0.1)

    def test_extract_mmr_partial_data(self):
        """Test avec données partielles : seulement team_mmr disponible."""
        skill_json = {
            "Value": [
                {
                    "Id": "xuid(1234567890123456)",
                    "Result": {
                        "TeamId": 0,
                        "TeamMmr": 1500.5,
                        # Pas de TeamMmrs ni d'autres joueurs avec TeamMmr
                    },
                },
            ]
        }

        result = _extract_mmr_from_skill(skill_json, "1234567890123456", 0)
        assert result is not None
        team_mmr, enemy_mmr = result
        assert team_mmr == 1500.5
        assert enemy_mmr is None

    def test_extract_mmr_only_enemy_mmr(self):
        """Test avec seulement enemy_mmr disponible (cas rare mais possible)."""
        skill_json = {
            "Value": [
                {
                    "Id": "xuid(1234567890123456)",
                    "Result": {
                        "TeamId": 0,
                        # Pas de TeamMmr pour ce joueur
                        "TeamMmrs": {"0": None, "1": 1450.3},
                    },
                },
                {
                    "Id": "xuid(9876543210987654)",
                    "Result": {
                        "TeamId": 1,
                        "TeamMmr": 1450.3,
                    },
                },
            ]
        }

        result = _extract_mmr_from_skill(skill_json, "1234567890123456", 0)
        assert result is not None
        team_mmr, enemy_mmr = result
        assert team_mmr is None
        assert enemy_mmr == 1450.3

    def test_extract_mmr_player_not_found(self):
        """Test quand le joueur n'est pas trouvé dans le JSON."""
        skill_json = {
            "Value": [
                {
                    "Id": "xuid(9876543210987654)",
                    "Result": {
                        "TeamId": 1,
                        "TeamMmr": 1450.3,
                    },
                },
            ]
        }

        result = _extract_mmr_from_skill(skill_json, "1234567890123456", 0)
        assert result is None

    def test_extract_mmr_invalid_json(self):
        """Test avec JSON invalide."""
        skill_json = {"Value": "not a list"}

        result = _extract_mmr_from_skill(skill_json, "1234567890123456", 0)
        assert result is None

    def test_extract_mmr_empty_value(self):
        """Test avec Value vide."""
        skill_json = {"Value": []}

        result = _extract_mmr_from_skill(skill_json, "1234567890123456", 0)
        assert result is None

    def test_extract_mmr_multiple_teams(self):
        """Test avec plusieurs équipes (plus de 2 équipes)."""
        skill_json = {
            "Value": [
                {
                    "Id": "xuid(1234567890123456)",
                    "Result": {
                        "TeamId": 0,
                        "TeamMmr": 1500.5,
                        "TeamMmrs": {"0": 1500.5, "1": 1450.3, "2": 1400.0},
                    },
                },
            ]
        }

        result = _extract_mmr_from_skill(skill_json, "1234567890123456", 0)
        assert result is not None
        team_mmr, enemy_mmr = result
        assert team_mmr == 1500.5
        # Devrait prendre le premier enemy_mmr trouvé (équipe 1)
        assert enemy_mmr == 1450.3

    def test_extract_mmr_team_id_fallback(self):
        """Test avec team_id fourni en paramètre si non trouvé dans Result."""
        skill_json = {
            "Value": [
                {
                    "Id": "xuid(1234567890123456)",
                    "Result": {
                        # Pas de TeamId dans Result
                        "TeamMmr": 1500.5,
                        "TeamMmrs": {"0": 1500.5, "1": 1450.3},
                    },
                },
            ]
        }

        # Fournir team_id en paramètre
        result = _extract_mmr_from_skill(skill_json, "1234567890123456", 0)
        assert result is not None
        team_mmr, enemy_mmr = result
        assert team_mmr == 1500.5
        assert enemy_mmr == 1450.3

    def test_extract_mmr_string_team_ids(self):
        """Test avec TeamId et TeamMmrs utilisant des strings."""
        skill_json = {
            "Value": [
                {
                    "Id": "xuid(1234567890123456)",
                    "Result": {
                        "TeamId": "0",  # String au lieu d'int
                        "TeamMmr": 1500.5,
                        "TeamMmrs": {"0": 1500.5, "1": 1450.3},
                    },
                },
            ]
        }

        result = _extract_mmr_from_skill(skill_json, "1234567890123456", None)
        assert result is not None
        team_mmr, enemy_mmr = result
        assert team_mmr == 1500.5
        assert enemy_mmr == 1450.3
