"""Tests pour vérifier que le score de performance est calculé dans timeseries.py.

Ce test vérifie que la régression où le score de performance n'était pas calculé
est corrigée.
"""

import polars as pl

from src.analysis.performance_score import compute_performance_series


def test_performance_score_is_computed():
    """Test que compute_performance_series fonctionne correctement."""
    # Créer un DataFrame de test
    df = pl.DataFrame(
        {
            "match_id": ["match_1", "match_2", "match_3"],
            "kills": [10, 15, 20],
            "deaths": [5, 4, 3],
            "assists": [3, 5, 7],
            "accuracy": [45.0, 50.0, 55.0],
            "kda": [2.6, 5.0, 9.0],
        }
    )

    # Calculer le score de performance
    scores = compute_performance_series(df, df)

    assert len(scores) == len(df), "Doit retourner un score pour chaque match"
    assert all(s is not None for s in scores), "Tous les scores doivent être calculés"
    assert all(isinstance(s, int | float) for s in scores), "Les scores doivent être numériques"


def test_performance_score_handles_missing_data():
    """Test que compute_performance_series gère correctement les données manquantes."""
    df = pl.DataFrame(
        {
            "match_id": ["match_1", "match_2"],
            "kills": [10, None],
            "deaths": [5, None],
            "assists": [3, None],
            "accuracy": [45.0, None],
            "kda": [2.6, None],
        }
    )

    scores = compute_performance_series(df, df)

    assert len(scores) == len(df)
    # Le premier match doit avoir un score
    assert scores[0] is not None


def test_timeseries_page_imports_compute_performance_series():
    """Test que timeseries.py importe compute_performance_series."""
    import src.ui.pages.timeseries as timeseries_module

    assert hasattr(
        timeseries_module, "compute_performance_series"
    ), "timeseries.py doit importer compute_performance_series"


def test_performance_score_column_exists_after_computation():
    """Test que la colonne performance_score existe après calcul."""
    df = pl.DataFrame(
        {
            "match_id": ["match_1", "match_2"],
            "kills": [10, 15],
            "deaths": [5, 4],
            "assists": [3, 5],
            "accuracy": [45.0, 50.0],
            "kda": [2.6, 5.0],
        }
    )

    scores = compute_performance_series(df, df)
    df_with_score = df.with_columns(scores.alias("performance_score"))

    assert (
        "performance_score" in df_with_score.columns
    ), "La colonne performance_score doit exister après calcul"
    assert (
        not df_with_score.get_column("performance_score").is_null().all()
    ), "Au moins certains scores doivent être calculés"
