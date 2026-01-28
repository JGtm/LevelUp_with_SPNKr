from __future__ import annotations

from src.analysis.mode_categories import (
    infer_custom_category_from_pair_name,
    infer_mode_super_category,
    normalize_pair_name_to_mode_ui,
)


class TestModeCategoriesCustom:
    """Tests pour l'alignement catégories custom (sidebar) <-> analyses."""

    def test_infer_mode_super_category_from_ui_labels(self) -> None:
        """Catégorie custom depuis les libellés UI traduits."""
        assert infer_mode_super_category("Arène : Assassin") == "Assassin"
        assert infer_mode_super_category("Communauté : Assassin") == "Assassin"
        assert infer_mode_super_category("Tactique : Assassin") == "Assassin"
        assert infer_mode_super_category("BTB : Capture du drapeau") == "BTB"
        assert infer_mode_super_category("BTB Heavies : Assassin") == "BTB"
        assert infer_mode_super_category("Super Fiesta : Assassin") == "Fiesta"
        assert infer_mode_super_category("Husky Raid : CDD") == "Fiesta"
        assert infer_mode_super_category("Classé : Assassin") == "Ranked"
        assert infer_mode_super_category("Baptême du feu : Roi de la colline héroïque") == "Firefight"
        assert infer_mode_super_category("Événement : Escalade") == "Other"

    def test_normalize_pair_name_to_mode_ui(self) -> None:
        """Normalisation pair_name -> mode_ui (doit enlever la carte / suffixes)."""
        assert normalize_pair_name_to_mode_ui("Arena:Slayer on Aquarius") == "Arène : Assassin"
        assert normalize_pair_name_to_mode_ui("Community:Slayer on Aquarius") == "Communauté : Assassin"
        assert normalize_pair_name_to_mode_ui("Ranked:Slayer on Aquarius") == "Classé : Assassin"
        assert normalize_pair_name_to_mode_ui(None) is None

    def test_infer_custom_category_from_pair_name(self) -> None:
        """Catégorie custom directement depuis pair_name (DB)."""
        assert infer_custom_category_from_pair_name("Arena:Slayer on Aquarius") == "Assassin"
        assert infer_custom_category_from_pair_name("Community:Slayer on Aquarius") == "Assassin"
        assert infer_custom_category_from_pair_name("Tactical:Slayer on Aquarius") == "Assassin"
        assert infer_custom_category_from_pair_name("BTB:CTF on Highpower") == "BTB"
        assert infer_custom_category_from_pair_name("BTB Heavies:Slayer") == "BTB"
        assert infer_custom_category_from_pair_name("Ranked:Slayer on Aquarius") == "Ranked"
        assert infer_custom_category_from_pair_name("Firefight:Heroic King of the Hill on SomeMap") == "Firefight"
        assert infer_custom_category_from_pair_name("Gruntpocalypse:Heroic KOTH on SomeMap") == "Firefight"
        assert infer_custom_category_from_pair_name(None) == "Other"
