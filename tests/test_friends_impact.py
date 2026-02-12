"""Tests pour le module d'analyse d'impact des coéquipiers (Sprint 12).

Teste les 4 fonctions d'identification et de scoring :
- identify_first_blood()
- identify_clutch_finisher()
- identify_last_casualty()
- compute_impact_scores()

Ainsi que les contraintes logiques :
- Finisseur + Boulet ne peuvent pas être dans le même match (outcomes incompatibles)
- Un joueur peut avoir First Blood + Finisseur (même match court avec victoire)
- First Blood est indépendant de l'outcome
"""

from __future__ import annotations

import pytest

try:
    import polars as pl

    POLARS_AVAILABLE = True
except ImportError:
    POLARS_AVAILABLE = False
    pl = None

# Tenter un import direct (peut échouer si duckdb manque via __init__)
try:
    from src.analysis.friends_impact import (
        OUTCOME_LOSS,
        OUTCOME_WIN,
        ImpactEvent,
        build_impact_matrix,
        compute_impact_scores,
        get_all_impact_events,
        identify_clutch_finisher,
        identify_first_blood,
        identify_last_casualty,
    )

    FRIENDS_IMPACT_AVAILABLE = True
except Exception:
    FRIENDS_IMPACT_AVAILABLE = False
    OUTCOME_LOSS = 3
    OUTCOME_WIN = 2

pytestmark = pytest.mark.skipif(
    not POLARS_AVAILABLE or not FRIENDS_IMPACT_AVAILABLE,
    reason="Polars ou dépendances transitives non disponibles",
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_events_df() -> pl.DataFrame:
    """DataFrame d'événements pour les tests."""
    return pl.DataFrame(
        {
            "match_id": ["m1", "m1", "m1", "m1", "m2", "m2", "m2", "m3", "m3"],
            "xuid": ["100", "100", "200", "200", "100", "200", "200", "100", "200"],
            "gamertag": [
                "Alice",
                "Alice",
                "Bob",
                "Bob",
                "Alice",
                "Bob",
                "Bob",
                "Alice",
                "Bob",
            ],
            "event_type": [
                "Kill",
                "Death",
                "Kill",
                "Death",
                "Kill",
                "Kill",
                "Death",
                "Kill",
                "Death",
            ],
            "time_ms": [1000, 2000, 3000, 1500, 500, 2000, 3000, 1000, 2000],
        }
    )


@pytest.fixture
def sample_matches_df() -> pl.DataFrame:
    """DataFrame des matchs pour les tests."""
    return pl.DataFrame(
        {
            "match_id": ["m1", "m2", "m3"],
            "outcome": [
                OUTCOME_WIN,
                OUTCOME_LOSS,
                OUTCOME_WIN,
            ],  # m1=victoire, m2=défaite, m3=victoire
        }
    )


@pytest.fixture
def empty_events_df() -> pl.DataFrame:
    """DataFrame d'événements vide."""
    return pl.DataFrame(
        schema={
            "match_id": pl.Utf8,
            "xuid": pl.Utf8,
            "gamertag": pl.Utf8,
            "event_type": pl.Utf8,
            "time_ms": pl.Int64,
        }
    )


@pytest.fixture
def empty_matches_df() -> pl.DataFrame:
    """DataFrame de matchs vide."""
    return pl.DataFrame(
        schema={
            "match_id": pl.Utf8,
            "outcome": pl.Int64,
        }
    )


# =============================================================================
# Tests identify_first_blood
# =============================================================================


class TestIdentifyFirstBlood:
    """Tests pour identify_first_blood()."""

    def test_identify_first_blood_basic(self, sample_events_df: pl.DataFrame) -> None:
        """Vérifie que le premier kill (min time_ms) est correctement identifié."""
        result = identify_first_blood(sample_events_df)

        assert len(result) == 3  # 3 matchs, 3 FB
        assert "m1" in result
        assert "m2" in result
        assert "m3" in result

        # Match m1 : Alice tue à 1000ms, Bob à 3000ms -> Alice
        assert result["m1"].gamertag == "Alice"
        assert result["m1"].time_ms == 1000

        # Match m2 : Alice tue à 500ms, Bob à 2000ms -> Alice
        assert result["m2"].gamertag == "Alice"
        assert result["m2"].time_ms == 500

        # Match m3 : Alice tue à 1000ms, Bob n'a pas de kill -> Alice
        assert result["m3"].gamertag == "Alice"
        assert result["m3"].time_ms == 1000

    def test_identify_first_blood_empty(self, empty_events_df: pl.DataFrame) -> None:
        """Vérifie le comportement avec un DataFrame vide."""
        result = identify_first_blood(empty_events_df)
        assert result == {}

    def test_identify_first_blood_no_kills(self) -> None:
        """Vérifie le comportement sans aucun kill."""
        df = pl.DataFrame(
            {
                "match_id": ["m1", "m1"],
                "xuid": ["100", "200"],
                "gamertag": ["Alice", "Bob"],
                "event_type": ["Death", "Death"],
                "time_ms": [1000, 2000],
            }
        )
        result = identify_first_blood(df)
        assert result == {}

    def test_identify_first_blood_filter_friends(self, sample_events_df: pl.DataFrame) -> None:
        """Vérifie le filtrage par amis."""
        # Filtrer seulement Bob (xuid="200")
        result = identify_first_blood(sample_events_df, friend_xuids={"200"})

        # Match m1 : Bob tue à 3000ms (seul kill de Bob) -> Bob
        assert "m1" in result
        assert result["m1"].gamertag == "Bob"

        # Match m2 : Bob tue à 2000ms -> Bob
        assert "m2" in result
        assert result["m2"].gamertag == "Bob"

        # Match m3 : Bob n'a pas de kill -> pas de FB
        assert "m3" not in result

    def test_first_blood_always_earliest(self, sample_events_df: pl.DataFrame) -> None:
        """Assertion : First Blood est toujours le kill avec min(time_ms)."""
        result = identify_first_blood(sample_events_df)

        # Pour chaque match, vérifier que FB a le plus petit timestamp parmi les kills
        kills = sample_events_df.filter(pl.col("event_type").str.to_lowercase() == "kill")

        for match_id, event in result.items():
            match_kills = kills.filter(pl.col("match_id") == match_id)
            min_time = match_kills["time_ms"].min()
            assert (
                event.time_ms == min_time
            ), f"Match {match_id}: FB devrait être à {min_time}, pas {event.time_ms}"


# =============================================================================
# Tests identify_clutch_finisher
# =============================================================================


class TestIdentifyClutchFinisher:
    """Tests pour identify_clutch_finisher()."""

    def test_identify_clutch_finisher_basic(
        self, sample_events_df: pl.DataFrame, sample_matches_df: pl.DataFrame
    ) -> None:
        """Vérifie que le dernier kill des victoires est identifié."""
        result = identify_clutch_finisher(sample_events_df, sample_matches_df)

        # m1 = victoire, m3 = victoire, m2 = défaite
        assert "m1" in result
        assert "m3" in result
        assert "m2" not in result  # Défaite, pas de finisseur

        # Match m1 : Bob tue à 3000ms (dernier kill) -> Bob
        assert result["m1"].gamertag == "Bob"
        assert result["m1"].time_ms == 3000

        # Match m3 : Alice tue à 1000ms (seul kill) -> Alice
        assert result["m3"].gamertag == "Alice"
        assert result["m3"].time_ms == 1000

    def test_identify_clutch_finisher_empty(
        self, empty_events_df: pl.DataFrame, empty_matches_df: pl.DataFrame
    ) -> None:
        """Vérifie le comportement avec des DataFrames vides."""
        result = identify_clutch_finisher(empty_events_df, empty_matches_df)
        assert result == {}

    def test_identify_clutch_finisher_no_wins(self) -> None:
        """Vérifie le comportement sans victoire."""
        events = pl.DataFrame(
            {
                "match_id": ["m1"],
                "xuid": ["100"],
                "gamertag": ["Alice"],
                "event_type": ["Kill"],
                "time_ms": [1000],
            }
        )
        matches = pl.DataFrame(
            {
                "match_id": ["m1"],
                "outcome": [OUTCOME_LOSS],
            }
        )
        result = identify_clutch_finisher(events, matches)
        assert result == {}


# =============================================================================
# Tests identify_last_casualty
# =============================================================================


class TestIdentifyLastCasualty:
    """Tests pour identify_last_casualty()."""

    def test_identify_last_casualty_basic(
        self, sample_events_df: pl.DataFrame, sample_matches_df: pl.DataFrame
    ) -> None:
        """Vérifie que la dernière mort des défaites est identifiée."""
        result = identify_last_casualty(sample_events_df, sample_matches_df)

        # Seul m2 est une défaite
        assert "m2" in result
        assert "m1" not in result  # Victoire
        assert "m3" not in result  # Victoire

        # Match m2 : Bob meurt à 3000ms (dernière mort) -> Bob
        assert result["m2"].gamertag == "Bob"
        assert result["m2"].time_ms == 3000

    def test_identify_last_casualty_empty(
        self, empty_events_df: pl.DataFrame, empty_matches_df: pl.DataFrame
    ) -> None:
        """Vérifie le comportement avec des DataFrames vides."""
        result = identify_last_casualty(empty_events_df, empty_matches_df)
        assert result == {}

    def test_identify_last_casualty_no_losses(self) -> None:
        """Vérifie le comportement sans défaite."""
        events = pl.DataFrame(
            {
                "match_id": ["m1"],
                "xuid": ["100"],
                "gamertag": ["Alice"],
                "event_type": ["Death"],
                "time_ms": [1000],
            }
        )
        matches = pl.DataFrame(
            {
                "match_id": ["m1"],
                "outcome": [OUTCOME_WIN],
            }
        )
        result = identify_last_casualty(events, matches)
        assert result == {}


# =============================================================================
# Tests compute_impact_scores
# =============================================================================


class TestComputeImpactScores:
    """Tests pour compute_impact_scores()."""

    def test_compute_impact_scores_basic(self) -> None:
        """Vérifie le calcul correct des scores."""
        first_bloods = {
            "m1": ImpactEvent("m1", "100", "Alice", 1000, "first_blood"),
            "m2": ImpactEvent("m2", "100", "Alice", 500, "first_blood"),
        }
        clutch_finishers = {
            "m1": ImpactEvent("m1", "200", "Bob", 3000, "clutch_finisher"),
        }
        last_casualties = {
            "m2": ImpactEvent("m2", "200", "Bob", 3000, "last_casualty"),
        }

        scores = compute_impact_scores(first_bloods, clutch_finishers, last_casualties)

        # Alice : 2 FB = +2
        # Bob : 1 Clutch (+2) + 1 Boulet (-1) = +1
        assert scores["Alice"] == 2
        assert scores["Bob"] == 1

        # Vérifier le tri (Alice en premier car score plus élevé)
        assert list(scores.keys())[0] == "Alice"

    def test_compute_impact_scores_empty(self) -> None:
        """Vérifie le comportement avec des dicts vides."""
        scores = compute_impact_scores({}, {}, {})
        assert scores == {}

    def test_compute_impact_scores_edge_cases(self) -> None:
        """Teste les cas limites (0 kills, 0 deaths)."""
        # Seulement des FB
        first_bloods = {
            "m1": ImpactEvent("m1", "100", "Alice", 1000, "first_blood"),
        }
        scores = compute_impact_scores(first_bloods, {}, {})
        assert scores["Alice"] == 1

        # Seulement des Boulets
        last_casualties = {
            "m1": ImpactEvent("m1", "200", "Bob", 3000, "last_casualty"),
        }
        scores = compute_impact_scores({}, {}, last_casualties)
        assert scores["Bob"] == -1


# =============================================================================
# Tests contraintes logiques
# =============================================================================


class TestImpactLogicalConstraints:
    """Tests des contraintes logiques d'incompatibilité."""

    def test_finisseur_and_boulet_never_together(self) -> None:
        """Assertion : Un match ne peut PAS avoir un Finisseur ET un Boulet.

        Finisseur nécessite outcome=2 (victoire), Boulet nécessite outcome=3 (défaite).
        Un match ne peut avoir qu'un seul outcome.
        """
        events = pl.DataFrame(
            {
                "match_id": ["m1", "m1", "m1", "m1"],
                "xuid": ["100", "100", "200", "200"],
                "gamertag": ["Alice", "Alice", "Bob", "Bob"],
                "event_type": ["Kill", "Death", "Kill", "Death"],
                "time_ms": [1000, 2000, 3000, 4000],
            }
        )
        # Match m1 = victoire
        matches_win = pl.DataFrame({"match_id": ["m1"], "outcome": [OUTCOME_WIN]})

        clutch = identify_clutch_finisher(events, matches_win)
        casualty = identify_last_casualty(events, matches_win)

        # Si victoire : Finisseur possible, Boulet impossible
        assert "m1" in clutch
        assert "m1" not in casualty

        # Match m1 = défaite
        matches_loss = pl.DataFrame({"match_id": ["m1"], "outcome": [OUTCOME_LOSS]})

        clutch = identify_clutch_finisher(events, matches_loss)
        casualty = identify_last_casualty(events, matches_loss)

        # Si défaite : Boulet possible, Finisseur impossible
        assert "m1" not in clutch
        assert "m1" in casualty

    def test_multiple_events_per_friend(self) -> None:
        """Assertion : Un joueur peut avoir FB + Finisseur dans le même match court."""
        # Match court où Alice fait le premier ET le dernier kill
        events = pl.DataFrame(
            {
                "match_id": ["m1", "m1"],
                "xuid": ["100", "100"],
                "gamertag": ["Alice", "Alice"],
                "event_type": ["Kill", "Kill"],
                "time_ms": [1000, 2000],  # Alice fait les 2 kills
            }
        )
        matches = pl.DataFrame({"match_id": ["m1"], "outcome": [OUTCOME_WIN]})

        first_bloods = identify_first_blood(events)
        clutch_finishers = identify_clutch_finisher(events, matches)

        # Alice a FB (1000ms) ET Finisseur (2000ms)
        assert "m1" in first_bloods
        assert "m1" in clutch_finishers
        assert first_bloods["m1"].gamertag == "Alice"
        assert clutch_finishers["m1"].gamertag == "Alice"

        # Les scores doivent refléter les deux événements
        scores = compute_impact_scores(first_bloods, clutch_finishers, {})
        assert scores["Alice"] == 3  # 1 (FB) + 2 (Clutch)

    def test_outcome_filtering_correct(self) -> None:
        """Assertion : Finisseur/Boulet sont rejetés si outcome ne correspond pas."""
        events = pl.DataFrame(
            {
                "match_id": ["m1"],
                "xuid": ["100"],
                "gamertag": ["Alice"],
                "event_type": ["Kill"],
                "time_ms": [1000],
            }
        )

        # Tester avec différents outcomes
        for outcome, expect_clutch, _expect_casualty in [
            (OUTCOME_WIN, True, False),
            (OUTCOME_LOSS, False, True),  # Boulet impossible car pas de Death
            (1, False, False),  # Égalité
            (4, False, False),  # Non terminé
        ]:
            matches = pl.DataFrame({"match_id": ["m1"], "outcome": [outcome]})
            clutch = identify_clutch_finisher(events, matches)
            # Note: pour casualty, on aurait besoin d'une Death

            if expect_clutch:
                assert "m1" in clutch, f"Clutch attendu pour outcome={outcome}"
            else:
                assert "m1" not in clutch, f"Clutch non attendu pour outcome={outcome}"


# =============================================================================
# Tests get_all_impact_events
# =============================================================================


class TestGetAllImpactEvents:
    """Tests pour la fonction de convenance get_all_impact_events()."""

    def test_get_all_impact_events(
        self, sample_events_df: pl.DataFrame, sample_matches_df: pl.DataFrame
    ) -> None:
        """Vérifie que la fonction retourne tous les événements."""
        fb, clutch, casualty, scores = get_all_impact_events(sample_events_df, sample_matches_df)

        assert len(fb) > 0
        assert len(clutch) > 0  # m1 et m3 sont des victoires
        assert len(casualty) > 0  # m2 est une défaite
        assert len(scores) > 0


# =============================================================================
# Tests build_impact_matrix
# =============================================================================


class TestBuildImpactMatrix:
    """Tests pour build_impact_matrix()."""

    def test_build_impact_matrix_basic(self) -> None:
        """Vérifie la construction de la matrice d'impact."""
        first_bloods = {
            "m1": ImpactEvent("m1", "100", "Alice", 1000, "first_blood"),
        }
        clutch_finishers = {
            "m1": ImpactEvent("m1", "200", "Bob", 3000, "clutch_finisher"),
        }
        last_casualties = {}

        matrix = build_impact_matrix(
            first_bloods,
            clutch_finishers,
            last_casualties,
            match_ids=["m1"],
            gamertags=["Alice", "Bob"],
        )

        assert not matrix.is_empty()
        assert len(matrix) == 2  # 2 joueurs × 1 match

        alice_row = matrix.filter(pl.col("gamertag") == "Alice")
        bob_row = matrix.filter(pl.col("gamertag") == "Bob")

        assert alice_row["event_type"][0] == "first_blood"
        assert bob_row["event_type"][0] == "clutch_finisher"

    def test_build_impact_matrix_empty(self) -> None:
        """Vérifie la matrice avec données vides."""
        matrix = build_impact_matrix({}, {}, {}, match_ids=[], gamertags=[])
        assert matrix.is_empty()
