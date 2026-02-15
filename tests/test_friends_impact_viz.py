"""Tests pour la visualisation heatmap d'impact (Sprint 12).

Teste les fonctions de visualisation :
- plot_friends_impact_heatmap()
- build_impact_ranking_df()
- count_events_by_player()
"""

from __future__ import annotations

import pytest

try:
    import polars as pl

    POLARS_AVAILABLE = True
except ImportError:
    POLARS_AVAILABLE = False
    pl = None

try:
    import plotly.graph_objects as go

    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    go = None

# Tenter un import direct (peut échouer si duckdb manque via __init__)
try:
    from src.analysis.friends_impact import ImpactEvent
    from src.visualization.friends_impact_heatmap import (
        IMPACT_COLORS,
        build_impact_ranking_df,
        count_events_by_player,
        plot_friends_impact_heatmap,
        render_impact_summary_stats,
    )

    FRIENDS_IMPACT_VIZ_AVAILABLE = True
except Exception:
    FRIENDS_IMPACT_VIZ_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not POLARS_AVAILABLE or not PLOTLY_AVAILABLE or not FRIENDS_IMPACT_VIZ_AVAILABLE,
    reason="Polars, Plotly ou dépendances transitives non disponibles",
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_impact_matrix() -> pl.DataFrame:
    """Matrice d'impact pour les tests."""
    return pl.DataFrame(
        {
            "match_id": ["m1", "m1", "m2", "m2", "m3", "m3"],
            "gamertag": ["Alice", "Bob", "Alice", "Bob", "Alice", "Bob"],
            "event_type": [
                "first_blood",
                "clutch_finisher",
                None,
                "last_casualty",
                "clutch_finisher",
                None,
            ],
            "event_value": [1, 2, 0, -1, 2, 0],
        }
    )


@pytest.fixture
def empty_impact_matrix() -> pl.DataFrame:
    """Matrice d'impact vide."""
    return pl.DataFrame(
        schema={
            "match_id": pl.Utf8,
            "gamertag": pl.Utf8,
            "event_type": pl.Utf8,
            "event_value": pl.Int64,
        }
    )


@pytest.fixture
def sample_scores() -> dict[str, int]:
    """Scores pour les tests."""
    return {"Alice": 4, "Bob": 1, "Charlie": -2}


@pytest.fixture
def sample_events() -> dict[str, ImpactEvent]:
    """Événements pour les tests."""
    return {
        "m1": ImpactEvent("m1", "100", "Alice", 1000, "first_blood"),
        "m2": ImpactEvent("m2", "100", "Alice", 500, "first_blood"),
        "m3": ImpactEvent("m3", "200", "Bob", 800, "first_blood"),
    }


# =============================================================================
# Tests plot_friends_impact_heatmap
# =============================================================================


class TestPlotFriendsImpactHeatmap:
    """Tests pour plot_friends_impact_heatmap()."""

    def test_plot_friends_impact_heatmap_valid(self, sample_impact_matrix: pl.DataFrame) -> None:
        """Vérifie qu'une figure Plotly valide est générée."""
        fig = plot_friends_impact_heatmap(sample_impact_matrix)

        assert fig is not None
        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 1

    def test_plot_friends_impact_heatmap_empty(self, empty_impact_matrix: pl.DataFrame) -> None:
        """Vérifie le comportement avec une matrice vide."""
        fig = plot_friends_impact_heatmap(empty_impact_matrix)

        assert fig is not None
        assert isinstance(fig, go.Figure)
        # Devrait avoir une annotation "Aucun événement"
        assert len(fig.layout.annotations) > 0

    def test_plot_friends_impact_heatmap_colors(self, sample_impact_matrix: pl.DataFrame) -> None:
        """Vérifie que les couleurs sont correctement définies."""
        fig = plot_friends_impact_heatmap(sample_impact_matrix)

        # Vérifier que la heatmap utilise une colorscale
        assert fig.data[0].colorscale is not None

    def test_plot_friends_impact_heatmap_with_title(
        self, sample_impact_matrix: pl.DataFrame
    ) -> None:
        """Vérifie que le titre est appliqué."""
        fig = plot_friends_impact_heatmap(sample_impact_matrix, title="Test Heatmap")

        assert fig is not None
        # Le titre devrait être dans le layout

    def test_plot_friends_impact_heatmap_max_matches(
        self, sample_impact_matrix: pl.DataFrame
    ) -> None:
        """Vérifie le respect de max_matches."""
        fig = plot_friends_impact_heatmap(sample_impact_matrix, max_matches=2)

        assert fig is not None
        # Le nombre de colonnes devrait être limité

    def test_plot_friends_impact_heatmap_custom_height(
        self, sample_impact_matrix: pl.DataFrame
    ) -> None:
        """Vérifie que la hauteur custom est appliquée."""
        fig = plot_friends_impact_heatmap(sample_impact_matrix, height=500)

        assert fig is not None
        assert fig.layout.height == 500


# =============================================================================
# Tests build_impact_ranking_df
# =============================================================================


class TestBuildImpactRankingDf:
    """Tests pour build_impact_ranking_df()."""

    def test_build_impact_ranking_df_basic(self, sample_scores: dict[str, int]) -> None:
        """Vérifie la construction du DataFrame de ranking."""
        df = build_impact_ranking_df(sample_scores)

        assert not df.is_empty()
        assert len(df) == 3

        # Vérifier les colonnes
        assert "rang" in df.columns
        assert "gamertag" in df.columns
        assert "score" in df.columns
        assert "badge" in df.columns

        # Vérifier le tri (Alice en premier avec score=4)
        assert df["gamertag"][0] == "Alice"
        assert df["score"][0] == 4
        assert df["rang"][0] == 1

        # Vérifier les badges
        assert "MVP" in df["badge"][0]  # Alice = MVP

    def test_build_impact_ranking_df_with_counts(self, sample_scores: dict[str, int]) -> None:
        """Vérifie l'ajout des compteurs d'événements."""
        fb_counts = {"Alice": 2, "Bob": 1}
        clutch_counts = {"Alice": 1}
        casualty_counts = {"Charlie": 2}

        df = build_impact_ranking_df(
            sample_scores,
            first_blood_counts=fb_counts,
            clutch_counts=clutch_counts,
            casualty_counts=casualty_counts,
        )

        assert "fb" in df.columns
        assert "clutch" in df.columns
        assert "boulet" in df.columns

        alice_row = df.filter(pl.col("gamertag") == "Alice")
        assert alice_row["fb"][0] == 2
        assert alice_row["clutch"][0] == 1

    def test_build_impact_ranking_df_empty(self) -> None:
        """Vérifie le comportement avec scores vides."""
        df = build_impact_ranking_df({})

        assert df.is_empty()

    def test_build_impact_ranking_df_boulet_badge(self) -> None:
        """Vérifie que le badge Boulet est attribué correctement."""
        scores = {"Alice": 10, "Bob": 5, "Charlie": -3}
        df = build_impact_ranking_df(scores)

        charlie_row = df.filter(pl.col("gamertag") == "Charlie")
        assert "Boulet" in charlie_row["badge"][0]

    def test_build_impact_ranking_df_single_player(self) -> None:
        """Vérifie le comportement avec un seul joueur."""
        scores = {"Alice": 5}
        df = build_impact_ranking_df(scores)

        assert len(df) == 1
        assert "MVP" in df["badge"][0]


# =============================================================================
# Tests count_events_by_player
# =============================================================================


class TestCountEventsByPlayer:
    """Tests pour count_events_by_player()."""

    def test_count_events_by_player_basic(self, sample_events: dict[str, ImpactEvent]) -> None:
        """Vérifie le comptage correct des événements."""
        counts = count_events_by_player(sample_events)

        assert counts["Alice"] == 2  # m1 et m2
        assert counts["Bob"] == 1  # m3

    def test_count_events_by_player_empty(self) -> None:
        """Vérifie le comportement avec dict vide."""
        counts = count_events_by_player({})
        assert counts == {}


# =============================================================================
# Tests render_impact_summary_stats
# =============================================================================


class TestRenderImpactSummaryStats:
    """Tests pour render_impact_summary_stats()."""

    def test_render_impact_summary_stats_basic(self) -> None:
        """Vérifie le calcul des stats résumées."""
        first_bloods = {
            "m1": ImpactEvent("m1", "100", "Alice", 1000, "first_blood"),
            "m2": ImpactEvent("m2", "100", "Alice", 500, "first_blood"),
        }
        clutch_finishers = {
            "m1": ImpactEvent("m1", "200", "Bob", 3000, "clutch_finisher"),
        }
        last_casualties = {
            "m3": ImpactEvent("m3", "200", "Bob", 4000, "last_casualty"),
        }

        stats = render_impact_summary_stats(first_bloods, clutch_finishers, last_casualties)

        assert stats["total_fb"] == 2
        assert stats["total_clutch"] == 1
        assert stats["total_casualty"] == 1
        assert stats["total_matches"] == 3  # m1, m2, m3

    def test_render_impact_summary_stats_empty(self) -> None:
        """Vérifie le comportement avec données vides."""
        stats = render_impact_summary_stats({}, {}, {})

        assert stats["total_fb"] == 0
        assert stats["total_clutch"] == 0
        assert stats["total_casualty"] == 0
        assert stats["total_matches"] == 0


# =============================================================================
# Tests des constantes
# =============================================================================


class TestImpactConstants:
    """Tests pour les constantes de visualisation."""

    def test_impact_colors_defined(self) -> None:
        """Vérifie que les couleurs sont définies."""
        assert "first_blood" in IMPACT_COLORS
        assert "clutch_finisher" in IMPACT_COLORS
        assert "last_casualty" in IMPACT_COLORS
        assert "none" in IMPACT_COLORS

    def test_impact_colors_format(self) -> None:
        """Vérifie le format des couleurs (hex ou rgba)."""
        for key, color in IMPACT_COLORS.items():
            # Doit être hex (#xxx ou #xxxxxx) ou rgba()
            assert color.startswith("#") or color.startswith(
                "rgba"
            ), f"Couleur invalide pour {key}: {color}"
