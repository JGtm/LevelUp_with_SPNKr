"""Tests pour la logique avancée de calcul des sessions.

Teste :
1. compute_sessions_with_context_polars() avec changement de coéquipiers
2. compute_sessions_with_context_polars() avec gap temporel
3. Cohérence entre backfill et UI
4. compute_teammates_signature()
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import polars as pl
import pytest

from src.analysis.sessions import compute_sessions_with_context_polars
from src.data.sync.transformers import compute_teammates_signature


def test_compute_sessions_with_teammates_change():
    """Test que changement de coéquipiers crée une nouvelle session."""
    # Créer un DataFrame avec changement de teammates_signature
    base_time = datetime(2026, 2, 5, 10, 0, 0, tzinfo=timezone.utc)

    df = pl.DataFrame(
        {
            "match_id": ["m1", "m2", "m3", "m4"],
            "start_time": [
                base_time,
                base_time + timedelta(minutes=10),
                base_time + timedelta(minutes=20),
                base_time + timedelta(minutes=30),
            ],
            "teammates_signature": [
                "xuid1,xuid2",
                "xuid1,xuid2",  # Même équipe
                "xuid3,xuid4",  # Changement d'équipe = nouvelle session
                "xuid3,xuid4",  # Même équipe
            ],
        }
    )

    result = compute_sessions_with_context_polars(
        df,
        gap_minutes=120,
        teammates_column="teammates_signature",
    )

    # Vérifier que session_id change au match m3
    sessions = result.select(["match_id", "session_id"]).sort("match_id")

    assert (
        sessions["session_id"][0] == sessions["session_id"][1]
    ), "m1 et m2 doivent être dans la même session"
    assert (
        sessions["session_id"][1] != sessions["session_id"][2]
    ), "m2 et m3 doivent être dans des sessions différentes"
    assert (
        sessions["session_id"][2] == sessions["session_id"][3]
    ), "m3 et m4 doivent être dans la même session"


def test_compute_sessions_with_gap():
    """Test que gap > gap_minutes crée une nouvelle session."""
    base_time = datetime(2026, 2, 5, 10, 0, 0, tzinfo=timezone.utc)

    df = pl.DataFrame(
        {
            "match_id": ["m1", "m2", "m3"],
            "start_time": [
                base_time,
                base_time + timedelta(minutes=10),  # 10 min après m1
                base_time + timedelta(minutes=150),  # 150 min après m1 (> 120 min)
            ],
            "teammates_signature": ["xuid1,xuid2", "xuid1,xuid2", "xuid1,xuid2"],
        }
    )

    result = compute_sessions_with_context_polars(
        df,
        gap_minutes=120,
        teammates_column="teammates_signature",
    )

    sessions = result.select(["match_id", "session_id"]).sort("match_id")

    assert (
        sessions["session_id"][0] == sessions["session_id"][1]
    ), "m1 et m2 doivent être dans la même session"
    assert (
        sessions["session_id"][1] != sessions["session_id"][2]
    ), "m2 et m3 doivent être dans des sessions différentes (gap > 120 min)"


def test_compute_sessions_without_teammates_column():
    """Test que la fonction fonctionne sans colonne teammates_signature."""
    base_time = datetime(2026, 2, 5, 10, 0, 0, tzinfo=timezone.utc)

    df = pl.DataFrame(
        {
            "match_id": ["m1", "m2", "m3"],
            "start_time": [
                base_time,
                base_time + timedelta(minutes=10),
                base_time + timedelta(minutes=150),
            ],
        }
    )

    result = compute_sessions_with_context_polars(
        df,
        gap_minutes=120,
        teammates_column=None,
    )

    # Doit fonctionner uniquement avec le gap temporel
    sessions = result.select(["match_id", "session_id"]).sort("match_id")

    assert sessions["session_id"][0] == sessions["session_id"][1]
    assert sessions["session_id"][1] != sessions["session_id"][2]


def test_compute_sessions_empty_dataframe():
    """Test avec DataFrame vide."""
    df = pl.DataFrame(
        {
            "match_id": [],
            "start_time": [],
        }
    )

    result = compute_sessions_with_context_polars(df, gap_minutes=120)

    assert result.is_empty() or "session_id" in result.columns
    assert "session_label" in result.columns


def test_compute_teammates_signature():
    """Test du calcul de teammates_signature."""
    match_json = {
        "Players": [
            {
                "PlayerId": "xuid(2533274823110022)",
                "LastTeamId": 0,
            },
            {
                "PlayerId": "xuid(2533274858283686)",
                "LastTeamId": 0,
            },
            {
                "PlayerId": "xuid(2533274883457349)",
                "LastTeamId": 0,
            },
            {
                "PlayerId": "xuid(9999999999999999)",
                "LastTeamId": 1,  # Équipe adverse
            },
        ],
    }

    my_xuid = "2533274823110022"
    my_team_id = 0

    signature = compute_teammates_signature(match_json, my_xuid, my_team_id)

    # Doit contenir les deux autres coéquipiers (triés)
    assert signature is not None
    assert "2533274858283686" in signature
    assert "2533274883457349" in signature
    assert "2533274823110022" not in signature  # Ne doit pas inclure moi-même
    assert "9999999999999999" not in signature  # Ne doit pas inclure l'adversaire

    # Vérifier le format (XUIDs triés séparés par virgule)
    xuids = signature.split(",")
    assert len(xuids) == 2
    assert xuids == sorted(xuids)  # Doit être trié


def test_compute_teammates_signature_no_teammates():
    """Test avec aucun coéquipier."""
    match_json = {
        "Players": [
            {
                "PlayerId": "xuid(2533274823110022)",
                "LastTeamId": 0,
            },
        ],
    }

    signature = compute_teammates_signature(match_json, "2533274823110022", 0)

    assert signature is None


def test_compute_teammates_signature_no_team():
    """Test avec team_id None."""
    match_json = {
        "Players": [
            {
                "PlayerId": "xuid(2533274823110022)",
                "LastTeamId": 0,
            },
        ],
    }

    signature = compute_teammates_signature(match_json, "2533274823110022", None)

    assert signature is None


def test_compute_sessions_null_teammates_signature_creates_break():
    """Test que NULL entre deux valeurs differentes cree une rupture de session."""
    base_time = datetime(2026, 2, 5, 10, 0, 0, tzinfo=timezone.utc)

    df = pl.DataFrame(
        {
            "match_id": ["m1", "m2", "m3"],
            "start_time": [
                base_time,
                base_time + timedelta(minutes=10),
                base_time + timedelta(minutes=20),
            ],
            "teammates_signature": ["xuid1,xuid2", None, "xuid3,xuid4"],
        }
    )

    result = compute_sessions_with_context_polars(
        df,
        gap_minutes=120,
        teammates_column="teammates_signature",
    )

    # NULL est une valeur distincte : m1 (xuid1,xuid2) != m2 (NULL) != m3 (xuid3,xuid4)
    # Donc 3 sessions
    sessions = result.select(["match_id", "session_id"]).sort("match_id")
    assert sessions["session_id"][0] != sessions["session_id"][1]
    assert sessions["session_id"][1] != sessions["session_id"][2]


def test_compute_sessions_all_null_same_session():
    """Test que plusieurs NULL consecutifs sans gap restent dans la meme session."""
    base_time = datetime(2026, 2, 5, 10, 0, 0, tzinfo=timezone.utc)

    df = pl.DataFrame(
        {
            "match_id": ["m1", "m2", "m3"],
            "start_time": [
                base_time,
                base_time + timedelta(minutes=10),
                base_time + timedelta(minutes=20),
            ],
            "teammates_signature": [None, None, None],
        }
    )

    result = compute_sessions_with_context_polars(
        df,
        gap_minutes=120,
        teammates_column="teammates_signature",
    )

    # Tous NULL = pas de rupture entre eux
    sessions = result.select(["match_id", "session_id"]).sort("match_id")
    assert sessions["session_id"][0] == sessions["session_id"][1] == sessions["session_id"][2]


def test_compute_sessions_first_match_always_session_0():
    """Test que le premier match a toujours session_id 0."""
    base_time = datetime(2026, 2, 5, 10, 0, 0, tzinfo=timezone.utc)

    df = pl.DataFrame(
        {
            "match_id": ["m1", "m2"],
            "start_time": [base_time, base_time + timedelta(minutes=10)],
            "teammates_signature": ["xuid1", "xuid1"],
        }
    )

    result = compute_sessions_with_context_polars(df, gap_minutes=120)

    assert result["session_id"][0] == 0
    assert result["session_id"][1] == 0


def test_compute_sessions_consistency():
    """Test que les sessions sont cohérentes entre plusieurs appels."""
    base_time = datetime(2026, 2, 5, 10, 0, 0, tzinfo=timezone.utc)

    df = pl.DataFrame(
        {
            "match_id": [f"m{i}" for i in range(10)],
            "start_time": [base_time + timedelta(minutes=i * 15) for i in range(10)],
            "teammates_signature": ["xuid1,xuid2"] * 5 + ["xuid3,xuid4"] * 5,
        }
    )

    result1 = compute_sessions_with_context_polars(df, gap_minutes=120)
    result2 = compute_sessions_with_context_polars(df, gap_minutes=120)

    # Les résultats doivent être identiques
    assert result1["session_id"].to_list() == result2["session_id"].to_list()
    assert result1["session_label"].to_list() == result2["session_label"].to_list()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
