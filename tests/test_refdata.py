"""Tests unitaires pour le module refdata.

Ce module teste les enums et fonctions utilitaires du module
src/data/domain/refdata.py
"""

import pytest

from src.data.domain.refdata import (
    ASSIST_SCORES,
    CATEGORY_TO_FR,
    KILL_SCORES,
    NEGATIVE_SCORES,
    OBJECTIVE_MODE_CATEGORIES,
    OBJECTIVE_SCORES,
    OUTCOME_TO_FR,
    PERSONAL_SCORE_DISPLAY_NAMES,
    PERSONAL_SCORE_POINTS,
    SLAYER_MODE_CATEGORIES,
    SPECIAL_MODE_CATEGORIES,
    VEHICLE_DESTRUCTION_SCORES,
    VEHICLE_HIJACK_SCORES,
    GameVariantCategory,
    Outcome,
    PersonalScoreNameId,
    get_category_name_fr,
    get_outcome_name_fr,
    get_personal_score_display_name,
    get_personal_score_points,
    is_assist_score,
    is_objective_mode,
    is_objective_score,
    is_slayer_mode,
)


class TestGameVariantCategory:
    """Tests pour l'enum GameVariantCategory."""

    def test_enum_values_exist(self):
        """Vérifie que les valeurs principales existent."""
        assert GameVariantCategory.MULTIPLAYER_SLAYER == 6
        assert GameVariantCategory.MULTIPLAYER_CTF == 15
        assert GameVariantCategory.MULTIPLAYER_ODDBALL == 18
        assert GameVariantCategory.MULTIPLAYER_STRONGHOLDS == 11
        assert GameVariantCategory.MULTIPLAYER_INFECTION == 22
        assert GameVariantCategory.MULTIPLAYER_FIREFIGHT == 42

    def test_unknown_value(self):
        """Vérifie la valeur UNKNOWN."""
        assert GameVariantCategory.UNKNOWN == -1

    def test_all_multiplayer_modes_have_prefix(self):
        """Vérifie que les modes multi ont le préfixe MULTIPLAYER."""
        multiplayer_modes = [m for m in GameVariantCategory if m.name.startswith("MULTIPLAYER_")]
        # Devrait avoir au moins 20 modes multiplayer
        assert len(multiplayer_modes) >= 20


class TestPersonalScoreNameId:
    """Tests pour l'enum PersonalScoreNameId."""

    def test_killed_player_value(self):
        """Vérifie la valeur de KILLED_PLAYER."""
        assert PersonalScoreNameId.KILLED_PLAYER == 1024030246

    def test_assist_values_exist(self):
        """Vérifie que les types d'assistance existent."""
        assert PersonalScoreNameId.KILL_ASSIST == 638246808
        assert PersonalScoreNameId.MARK_ASSIST == 152718958
        assert PersonalScoreNameId.SENSOR_ASSIST == 1267013266
        assert PersonalScoreNameId.EMP_ASSIST == 221060588
        assert PersonalScoreNameId.DRIVER_ASSIST == 963594075

    def test_objective_values_exist(self):
        """Vérifie que les types d'objectifs existent."""
        assert PersonalScoreNameId.FLAG_CAPTURED == 601966503
        assert PersonalScoreNameId.HILL_SCORED == 1032565232
        assert PersonalScoreNameId.ZONE_CAPTURED_100 == 757037588
        assert PersonalScoreNameId.POWER_SEED_SECURED == 2188620691

    def test_negative_values_exist(self):
        """Vérifie que les scores négatifs existent."""
        assert PersonalScoreNameId.BETRAYED_PLAYER == 911992497
        assert PersonalScoreNameId.SELF_DESTRUCTION == 249491819


class TestOutcome:
    """Tests pour l'enum Outcome."""

    def test_outcome_values(self):
        """Vérifie les valeurs de Outcome."""
        assert Outcome.WIN == 2
        assert Outcome.LOSS == 3
        assert Outcome.TIE == 1
        assert Outcome.DID_NOT_FINISH == 4


class TestCategoryMappings:
    """Tests pour les mappings de catégories."""

    def test_category_to_fr_has_main_modes(self):
        """Vérifie que les modes principaux ont une traduction."""
        assert CATEGORY_TO_FR[GameVariantCategory.MULTIPLAYER_SLAYER] == "Assassin"
        assert CATEGORY_TO_FR[GameVariantCategory.MULTIPLAYER_CTF] == "Capture de drapeau"
        assert CATEGORY_TO_FR[GameVariantCategory.MULTIPLAYER_ODDBALL] == "Balle"
        assert CATEGORY_TO_FR[GameVariantCategory.MULTIPLAYER_STRONGHOLDS] == "Bastions"
        assert CATEGORY_TO_FR[GameVariantCategory.MULTIPLAYER_INFECTION] == "Infection"

    def test_outcome_to_fr_has_all_values(self):
        """Vérifie que tous les résultats ont une traduction."""
        assert OUTCOME_TO_FR[Outcome.WIN] == "Victoire"
        assert OUTCOME_TO_FR[Outcome.LOSS] == "Défaite"
        assert OUTCOME_TO_FR[Outcome.TIE] == "Égalité"

    def test_personal_score_display_names_coverage(self):
        """Vérifie que les scores principaux ont un nom d'affichage."""
        assert PersonalScoreNameId.KILLED_PLAYER in PERSONAL_SCORE_DISPLAY_NAMES
        assert PersonalScoreNameId.KILL_ASSIST in PERSONAL_SCORE_DISPLAY_NAMES
        assert PersonalScoreNameId.FLAG_CAPTURED in PERSONAL_SCORE_DISPLAY_NAMES


class TestPersonalScorePoints:
    """Tests pour les points des scores personnels."""

    def test_killed_player_points(self):
        """Vérifie les points pour un kill."""
        assert PERSONAL_SCORE_POINTS[PersonalScoreNameId.KILLED_PLAYER] == 100

    def test_assist_points(self):
        """Vérifie les points pour les assistances."""
        assert PERSONAL_SCORE_POINTS[PersonalScoreNameId.KILL_ASSIST] == 50
        assert PERSONAL_SCORE_POINTS[PersonalScoreNameId.MARK_ASSIST] == 10
        assert PERSONAL_SCORE_POINTS[PersonalScoreNameId.EMP_ASSIST] == 50

    def test_objective_points(self):
        """Vérifie les points pour les objectifs."""
        assert PERSONAL_SCORE_POINTS[PersonalScoreNameId.FLAG_CAPTURED] == 300
        assert PERSONAL_SCORE_POINTS[PersonalScoreNameId.HILL_SCORED] == 100
        assert PERSONAL_SCORE_POINTS[PersonalScoreNameId.ZONE_CAPTURED_100] == 100

    def test_negative_points(self):
        """Vérifie les points négatifs."""
        assert PERSONAL_SCORE_POINTS[PersonalScoreNameId.BETRAYED_PLAYER] == -100
        assert PERSONAL_SCORE_POINTS[PersonalScoreNameId.SELF_DESTRUCTION] == -100


class TestScoreSets:
    """Tests pour les sets de regroupement."""

    def test_objective_scores_not_empty(self):
        """Vérifie que OBJECTIVE_SCORES n'est pas vide."""
        assert len(OBJECTIVE_SCORES) > 0
        assert PersonalScoreNameId.FLAG_CAPTURED in OBJECTIVE_SCORES
        assert PersonalScoreNameId.HILL_SCORED in OBJECTIVE_SCORES
        assert PersonalScoreNameId.ZONE_CAPTURED_100 in OBJECTIVE_SCORES

    def test_assist_scores_content(self):
        """Vérifie le contenu de ASSIST_SCORES."""
        assert PersonalScoreNameId.KILL_ASSIST in ASSIST_SCORES
        assert PersonalScoreNameId.MARK_ASSIST in ASSIST_SCORES
        assert PersonalScoreNameId.EMP_ASSIST in ASSIST_SCORES
        # KILLED_PLAYER ne doit PAS être dedans
        assert PersonalScoreNameId.KILLED_PLAYER not in ASSIST_SCORES

    def test_kill_scores_content(self):
        """Vérifie le contenu de KILL_SCORES."""
        assert PersonalScoreNameId.KILLED_PLAYER in KILL_SCORES
        assert PersonalScoreNameId.ELIMINATED_PLAYER in KILL_SCORES
        # Les assists ne doivent PAS être dedans
        assert PersonalScoreNameId.KILL_ASSIST not in KILL_SCORES

    def test_negative_scores_content(self):
        """Vérifie le contenu de NEGATIVE_SCORES."""
        assert PersonalScoreNameId.BETRAYED_PLAYER in NEGATIVE_SCORES
        assert PersonalScoreNameId.SELF_DESTRUCTION in NEGATIVE_SCORES
        assert len(NEGATIVE_SCORES) == 2

    def test_vehicle_scores_content(self):
        """Vérifie les sets de véhicules."""
        assert len(VEHICLE_DESTRUCTION_SCORES) > 10
        assert len(VEHICLE_HIJACK_SCORES) > 8
        assert PersonalScoreNameId.DESTROYED_WARTHOG in VEHICLE_DESTRUCTION_SCORES
        assert PersonalScoreNameId.HIJACKED_GHOST in VEHICLE_HIJACK_SCORES


class TestModeCategorySets:
    """Tests pour les sets de catégories de modes."""

    def test_objective_mode_categories(self):
        """Vérifie les modes à objectifs."""
        assert GameVariantCategory.MULTIPLAYER_CTF in OBJECTIVE_MODE_CATEGORIES
        assert GameVariantCategory.MULTIPLAYER_ODDBALL in OBJECTIVE_MODE_CATEGORIES
        assert GameVariantCategory.MULTIPLAYER_STRONGHOLDS in OBJECTIVE_MODE_CATEGORIES
        # Slayer ne doit PAS être dedans
        assert GameVariantCategory.MULTIPLAYER_SLAYER not in OBJECTIVE_MODE_CATEGORIES

    def test_slayer_mode_categories(self):
        """Vérifie les modes Slayer."""
        assert GameVariantCategory.MULTIPLAYER_SLAYER in SLAYER_MODE_CATEGORIES
        assert GameVariantCategory.MULTIPLAYER_FIESTA in SLAYER_MODE_CATEGORIES
        assert GameVariantCategory.MULTIPLAYER_SWAT in SLAYER_MODE_CATEGORIES
        # CTF ne doit PAS être dedans
        assert GameVariantCategory.MULTIPLAYER_CTF not in SLAYER_MODE_CATEGORIES

    def test_special_mode_categories(self):
        """Vérifie les modes spéciaux."""
        assert GameVariantCategory.MULTIPLAYER_INFECTION in SPECIAL_MODE_CATEGORIES
        assert GameVariantCategory.MULTIPLAYER_FIREFIGHT in SPECIAL_MODE_CATEGORIES

    def test_no_overlap_between_objective_and_slayer(self):
        """Vérifie qu'il n'y a pas de chevauchement objectifs/slayer."""
        overlap = OBJECTIVE_MODE_CATEGORIES & SLAYER_MODE_CATEGORIES
        assert len(overlap) == 0, f"Chevauchement trouvé : {overlap}"


class TestUtilityFunctions:
    """Tests pour les fonctions utilitaires."""

    def test_get_category_name_fr_with_enum(self):
        """Teste get_category_name_fr avec un enum."""
        result = get_category_name_fr(GameVariantCategory.MULTIPLAYER_SLAYER)
        assert result == "Assassin"

    def test_get_category_name_fr_with_int(self):
        """Teste get_category_name_fr avec un entier."""
        result = get_category_name_fr(6)  # MULTIPLAYER_SLAYER
        assert result == "Assassin"

    def test_get_category_name_fr_unknown(self):
        """Teste get_category_name_fr avec une valeur inconnue."""
        result = get_category_name_fr(9999)
        assert result == "Autre"

    def test_get_outcome_name_fr(self):
        """Teste get_outcome_name_fr."""
        assert get_outcome_name_fr(Outcome.WIN) == "Victoire"
        assert get_outcome_name_fr(2) == "Victoire"
        assert get_outcome_name_fr(9999) == "Inconnu"

    def test_get_personal_score_display_name(self):
        """Teste get_personal_score_display_name."""
        result = get_personal_score_display_name(PersonalScoreNameId.KILLED_PLAYER)
        assert result == "Joueur tué"

        result = get_personal_score_display_name(1024030246)
        assert result == "Joueur tué"

        result = get_personal_score_display_name(9999)
        assert result == "Score"

    def test_get_personal_score_points(self):
        """Teste get_personal_score_points."""
        assert get_personal_score_points(PersonalScoreNameId.KILLED_PLAYER) == 100
        assert get_personal_score_points(1024030246) == 100
        assert get_personal_score_points(PersonalScoreNameId.KILL_ASSIST) == 50
        assert get_personal_score_points(9999) == 0

    def test_is_objective_score(self):
        """Teste is_objective_score."""
        assert is_objective_score(PersonalScoreNameId.FLAG_CAPTURED) is True
        assert is_objective_score(601966503) is True  # FLAG_CAPTURED
        assert is_objective_score(PersonalScoreNameId.KILLED_PLAYER) is False
        assert is_objective_score(PersonalScoreNameId.KILL_ASSIST) is False

    def test_is_assist_score(self):
        """Teste is_assist_score."""
        assert is_assist_score(PersonalScoreNameId.KILL_ASSIST) is True
        assert is_assist_score(638246808) is True  # KILL_ASSIST
        assert is_assist_score(PersonalScoreNameId.KILLED_PLAYER) is False
        assert is_assist_score(PersonalScoreNameId.FLAG_CAPTURED) is False

    def test_is_objective_mode(self):
        """Teste is_objective_mode."""
        assert is_objective_mode(GameVariantCategory.MULTIPLAYER_CTF) is True
        assert is_objective_mode(15) is True  # CTF
        assert is_objective_mode(GameVariantCategory.MULTIPLAYER_SLAYER) is False

    def test_is_slayer_mode(self):
        """Teste is_slayer_mode."""
        assert is_slayer_mode(GameVariantCategory.MULTIPLAYER_SLAYER) is True
        assert is_slayer_mode(6) is True  # SLAYER
        assert is_slayer_mode(GameVariantCategory.MULTIPLAYER_FIESTA) is True
        assert is_slayer_mode(GameVariantCategory.MULTIPLAYER_CTF) is False


class TestDataIntegrity:
    """Tests d'intégrité des données."""

    def test_all_objective_scores_have_points(self):
        """Vérifie que tous les scores objectifs ont des points définis."""
        for score_id in OBJECTIVE_SCORES:
            assert score_id in PERSONAL_SCORE_POINTS, f"Score {score_id} n'a pas de points définis"

    def test_all_assist_scores_have_points(self):
        """Vérifie que tous les scores d'assistance ont des points définis."""
        for score_id in ASSIST_SCORES:
            assert score_id in PERSONAL_SCORE_POINTS, f"Score {score_id} n'a pas de points définis"

    def test_all_mapped_categories_are_valid_enums(self):
        """Vérifie que toutes les catégories mappées sont des enums valides."""
        for cat_value in CATEGORY_TO_FR:
            try:
                GameVariantCategory(cat_value)
            except ValueError:
                pytest.fail(f"Catégorie {cat_value} n'est pas un enum valide")

    def test_all_mapped_outcomes_are_valid_enums(self):
        """Vérifie que tous les résultats mappés sont des enums valides."""
        for outcome_value in OUTCOME_TO_FR:
            try:
                Outcome(outcome_value)
            except ValueError:
                pytest.fail(f"Outcome {outcome_value} n'est pas un enum valide")
