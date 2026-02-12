"""Tests 10C : Priorité adornment > rank_icon dans le hero HTML.

Vérifie que get_hero_html affiche l'adornment en priorité et
n'affiche l'icône de rang que si l'adornment est absent.
"""

from __future__ import annotations

from pathlib import Path

from src.ui.styles import get_hero_html


def _create_fake_image(tmp_dir: Path, name: str) -> str:
    """Crée un fichier PNG minimal pour les tests."""
    # PNG 1x1 transparent minimal
    png_header = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
        b"\r\n\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    path = tmp_dir / name
    path.write_bytes(png_header)
    return str(path)


class TestHeroAdornmentPriority:
    """10C.3.3 : L'adornment remplace l'icône rank quand présent."""

    def test_adornment_shown_when_available(self, tmp_path: Path) -> None:
        """Quand adornment_path est fourni, il est affiché avec --primary."""
        adornment = _create_fake_image(tmp_path, "adornment.png")
        rank_icon = _create_fake_image(tmp_path, "rank.png")

        html = get_hero_html(
            player_name="Spartan",
            rank_label="Héros",
            rank_icon_path=rank_icon,
            adornment_path=adornment,
        )

        assert "career-rank__adornment--primary" in html
        # L'icône de rang ne doit PAS apparaître quand adornment est dispo
        assert "career-rank__icon" not in html

    def test_rank_icon_fallback_when_no_adornment(self, tmp_path: Path) -> None:
        """Sans adornment, l'icône de rang standard est affichée."""
        rank_icon = _create_fake_image(tmp_path, "rank.png")

        html = get_hero_html(
            player_name="Spartan",
            rank_label="Sergent",
            rank_icon_path=rank_icon,
            adornment_path=None,
        )

        assert "career-rank__icon" in html
        assert "career-rank__adornment" not in html

    def test_no_rank_section_without_data(self) -> None:
        """Sans icône ni label, aucune section rank n'est rendue."""
        html = get_hero_html(
            player_name="Spartan",
            rank_label=None,
            rank_icon_path=None,
            adornment_path=None,
        )

        assert "career-rank" not in html

    def test_adornment_only_no_rank_icon(self, tmp_path: Path) -> None:
        """Adornment seul (sans rank_icon_path) → section affichée."""
        adornment = _create_fake_image(tmp_path, "adornment.png")

        html = get_hero_html(
            player_name="Spartan",
            rank_label="Héros",
            adornment_path=adornment,
        )

        assert "career-rank__adornment--primary" in html
        assert "career-rank__icon" not in html

    def test_label_only_without_icons(self) -> None:
        """Label seul (sans icônes) → section rendue avec texte."""
        html = get_hero_html(
            player_name="Spartan",
            rank_label="Recrue",
        )

        assert "career-rank__label" in html
        assert "Recrue" in html

    def test_empty_player_name_returns_default(self) -> None:
        """Sans nom de joueur, le hero par défaut est retourné."""
        html = get_hero_html(player_name="")
        assert "LevelUp" in html
        assert "career-rank" not in html
