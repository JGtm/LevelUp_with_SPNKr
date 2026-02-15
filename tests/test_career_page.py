"""Tests pour le composant carrière et la page associée.

Sprint 3B : Vérifie le composant gauge de progression et les fonctions
utilitaires de la page carrière.
"""

from __future__ import annotations

import plotly.graph_objects as go

from src.ui.career_ranks import format_career_rank_label_fr
from src.ui.components.career_progress_circle import create_career_progress_gauge


class TestCareerProgressGauge:
    """Tests pour le composant gauge de progression XP."""

    def test_returns_plotly_figure(self):
        """Vérifie que la gauge retourne un go.Figure valide."""
        fig = create_career_progress_gauge(
            current_xp=500,
            xp_for_next_rank=1000,
            progress_pct=50.0,
            rank_name_fr="Sergent - Argent II",
        )
        assert isinstance(fig, go.Figure)
        assert len(fig.data) > 0

    def test_max_rank_shows_100_percent(self):
        """Vérifie que is_max_rank force la progression à 100%."""
        fig = create_career_progress_gauge(
            current_xp=0,
            xp_for_next_rank=0,
            progress_pct=0.0,
            rank_name_fr="Héros",
            is_max_rank=True,
        )
        assert isinstance(fig, go.Figure)
        # La valeur de l'indicateur doit être 100
        assert fig.data[0].value == 100.0

    def test_zero_xp(self):
        """Vérifie que la gauge fonctionne avec XP=0."""
        fig = create_career_progress_gauge(
            current_xp=0,
            xp_for_next_rank=1000,
            progress_pct=0.0,
            rank_name_fr="Recrue",
        )
        assert isinstance(fig, go.Figure)
        assert fig.data[0].value == 0.0

    def test_full_progress(self):
        """Vérifie que la gauge fonctionne à 100% sans is_max_rank."""
        fig = create_career_progress_gauge(
            current_xp=1000,
            xp_for_next_rank=1000,
            progress_pct=100.0,
            rank_name_fr="Général - Or III",
        )
        assert isinstance(fig, go.Figure)
        assert fig.data[0].value == 100.0

    def test_custom_height(self):
        """Vérifie que la hauteur personnalisée est respectée."""
        fig = create_career_progress_gauge(
            current_xp=500,
            xp_for_next_rank=1000,
            progress_pct=50.0,
            rank_name_fr="Caporal - Bronze I",
            height=400,
        )
        assert fig.layout.height == 400


class TestCareerRankLabels:
    """Tests pour les labels FR de rang carrière."""

    def test_recruit_label(self):
        """Vérifie le label du rang Recrue (cas spécial sans tier)."""
        label = format_career_rank_label_fr(tier=None, title="Recruit", grade=None)
        assert label == "Recrue"

    def test_hero_label(self):
        """Vérifie le label du rang Héros (cas spécial sans tier)."""
        label = format_career_rank_label_fr(tier=None, title="Hero", grade=None)
        assert label == "Héros"

    def test_regular_rank_with_tier_and_grade(self):
        """Vérifie un rang normal avec tier et grade."""
        label = format_career_rank_label_fr(tier="Silver", title="Private", grade="2")
        assert label == "Soldat - Argent II"

    def test_rank_without_grade(self):
        """Vérifie un rang avec tier mais sans grade."""
        label = format_career_rank_label_fr(tier="Gold", title="Captain", grade=None)
        assert label == "Capitaine - Or"

    def test_rank_french_translation(self):
        """Vérifie les traductions FR principales."""
        assert (
            format_career_rank_label_fr(tier="Bronze", title="Corporal", grade="1")
            == "Caporal - Bronze I"
        )
        assert (
            format_career_rank_label_fr(tier="Platinum", title="Sergeant", grade="3")
            == "Sergent - Platine III"
        )
        assert (
            format_career_rank_label_fr(tier="Diamond", title="General", grade="1")
            == "Général - Diamant I"
        )
