"""Tests pour le module win_streaks (Sprint 7).

Teste :
1. Calcul des séries de victoires / défaites consécutives
2. Section "Score personnel par match" (barres colorées)
3. Section "Rang et score personnel"
4. Adaptation "Matchs Top" pour périodes < semaine
"""

from __future__ import annotations

import pytest

try:
    import polars as pl

    POLARS_AVAILABLE = True
except ImportError:
    POLARS_AVAILABLE = False
    pl = None

pytestmark = pytest.mark.skipif(
    not POLARS_AVAILABLE,
    reason="Polars non disponible",
)


# =============================================================================
# 7.2 — Séries de victoires / défaites
# =============================================================================


class TestWinStreaks:
    """Tests pour src/analysis/win_streaks.py (P6 §1)."""

    def test_compute_win_streaks_basic(self):
        """Calcul des séries de victoires sur un historique simple."""
        pass

    def test_compute_loss_streaks_basic(self):
        """Calcul des séries de défaites sur un historique simple."""
        pass

    def test_streak_reset_on_outcome_change(self):
        """La série est réinitialisée quand le résultat change."""
        pass

    def test_streak_with_ties_and_no_finish(self):
        """Ties et NoFinish ne prolongent pas les séries."""
        pass

    def test_longest_streak(self):
        """Identification de la plus longue série."""
        pass


# =============================================================================
# 7.1 — Score personnel par match (barres colorées)
# =============================================================================


class TestPersonalScorePerMatch:
    """Tests pour la section barres colorées score personnel (P6 §1)."""

    def test_score_bars_coloring(self):
        """Les barres sont colorées selon le résultat (win/loss)."""
        pass


# =============================================================================
# 7.3 — Rang et score personnel
# =============================================================================


class TestRankAndPersonalScore:
    """Tests pour la section rang et score personnel (P6 §1)."""

    def test_rank_score_correlation(self):
        """Corrélation entre rang CSR et score personnel."""
        pass


# =============================================================================
# 7.7 — Matchs Top adaptés périodes courtes
# =============================================================================


class TestMatchsTopShortPeriods:
    """Tests pour l'adaptation Matchs Top < semaine (P6 §6.1)."""

    def test_top_matches_short_period(self):
        """Matchs Top fonctionne sur des périodes < 7 jours."""
        pass
